import os
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

ARTIFACTS = Path(os.environ.get("MODEL_ARTIFACTS_PATH", "./ml/artifacts"))

# Validation split: train on pre-2001 history, test on 2001-present.
# This covers three out-of-sample recession events: 2001, 2008-09, 2020.
OOS_CUTOFF = "2001-01-01"


def _load_all_series(db_path: str = "./data/warehouse.duckdb") -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute("""
        SELECT series_id, observation_date, value
        FROM raw.economic_indicators
        WHERE value IS NOT NULL
        ORDER BY observation_date
    """).fetchdf()
    con.close()
    return df


def _to_monthly_panel(df: pd.DataFrame) -> pd.DataFrame:
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    pivot = df.pivot_table(
        index="observation_date", columns="series_id", values="value", aggfunc="mean"
    )
    return pivot.resample("MS").mean().ffill(limit=3)


def _build_features(monthly: pd.DataFrame) -> pd.DataFrame:
    feats = pd.DataFrame(index=monthly.index)

    if "T10Y2Y" in monthly.columns:
        feats["t10y2y"] = monthly["T10Y2Y"]
        feats["t10y2y_3m_chg"] = monthly["T10Y2Y"].diff(3)
        inv = (monthly["T10Y2Y"] < 0).astype(int)
        groups = (inv != inv.shift()).cumsum()
        feats["t10y2y_inv_months"] = inv.groupby(groups).cumsum()

    if "UNRATE" in monthly.columns:
        feats["unrate"] = monthly["UNRATE"]
        feats["unrate_3m_chg"] = monthly["UNRATE"].diff(3)
        feats["unrate_6m_chg"] = monthly["UNRATE"].diff(6)

    if "FEDFUNDS" in monthly.columns:
        feats["fedfunds"] = monthly["FEDFUNDS"]
        feats["fedfunds_6m_chg"] = monthly["FEDFUNDS"].diff(6)
        feats["fedfunds_12m_chg"] = monthly["FEDFUNDS"].diff(12)

    if "HOUST" in monthly.columns:
        feats["houst_6m_pct"] = monthly["HOUST"].pct_change(6, fill_method=None) * 100

    if "CPIAUCSL" in monthly.columns:
        feats["cpi_yoy"] = monthly["CPIAUCSL"].pct_change(12) * 100

    if "GDP" in monthly.columns:
        feats["gdp_yoy"] = monthly["GDP"].pct_change(12, fill_method=None) * 100

    return feats


def _oos_metrics(model, scaler, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    """Compute out-of-sample metrics. Returns None values if no positives in test set."""
    if len(y_test) == 0 or y_test.sum() == 0:
        return {"auc": None, "brier": None, "precision": None, "recall": None, "f1": None}

    X_scaled = scaler.transform(X_test)
    probs = model.predict_proba(X_scaled)[:, 1]
    preds = (probs >= 0.5).astype(int)

    return {
        "auc": round(float(roc_auc_score(y_test, probs)), 4),
        "brier": round(float(brier_score_loss(y_test, probs)), 4),
        "precision": round(float(precision_score(y_test, preds, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, preds, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, preds, zero_division=0)), 4),
        "n_test": int(len(y_test)),
        "n_recession_months": int(y_test.sum()),
        "test_period": f"{OOS_CUTOFF[:4]}–present",
    }


def train_recession_model(db_path: str = "./data/warehouse.duckdb") -> dict:
    df = _load_all_series(db_path)

    if "USREC" not in df["series_id"].unique():
        raise ValueError(
            "USREC not in database. Add it to DEFAULT_SERIES and re-run ingestion."
        )

    monthly = _to_monthly_panel(df)
    usrec = monthly["USREC"].fillna(0)

    feats = _build_features(monthly)
    feats["recession_now"] = usrec.reindex(feats.index, method="ffill").fillna(0)
    # Forward-looking target: any recession in the next 12 months
    feats["target"] = (
        usrec.reindex(feats.index, method="ffill")
        .fillna(0)
        .shift(-1)
        .rolling(12, min_periods=1)
        .max()
    )
    feats = feats.dropna()

    feature_cols = [c for c in feats.columns if c not in ("recession_now", "target")]
    X = feats[feature_cols].values
    y = feats["target"].values

    # --- Out-of-sample validation ---
    split = feats.index < OOS_CUTOFF
    X_train_v = X[split]
    y_train_v = y[split]
    X_test_v = X[~split]
    y_test_v = y[~split]

    scaler_v = StandardScaler().fit(X_train_v)
    model_v = LogisticRegression(C=0.5, class_weight="balanced", max_iter=1000, random_state=42)
    model_v.fit(scaler_v.transform(X_train_v), y_train_v)
    oos = _oos_metrics(model_v, scaler_v, X_test_v, y_test_v)

    # --- Production model: train on all data ---
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = LogisticRegression(C=0.5, class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_scaled, y)

    probs_full = model.predict_proba(X_scaled)[:, 1]
    in_sample_auc = round(float(roc_auc_score(y, probs_full)), 4)

    # Standardized coefficients — directly comparable because features are z-scored
    feature_importances = sorted(
        [{"feature": col, "coefficient": round(float(coef), 4)}
         for col, coef in zip(feature_cols, model.coef_[0])],
        key=lambda x: abs(x["coefficient"]),
        reverse=True,
    )

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "scaler": scaler,
            "feature_cols": feature_cols,
            "oos_metrics": oos,
            "feature_importances": feature_importances,
        },
        ARTIFACTS / "recession_model.joblib",
    )

    history = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "probability": round(float(probs_full[i]), 4),
            "recession": int(row["recession_now"]),
        }
        for i, (idx, row) in enumerate(feats.iterrows())
    ]

    return {
        "in_sample_auc": in_sample_auc,
        "oos_metrics": oos,
        "training_rows": len(X),
        "feature_importances": feature_importances,
        "history": history,
    }


def predict_recession(db_path: str = "./data/warehouse.duckdb") -> dict:
    artifact_path = ARTIFACTS / "recession_model.joblib"
    if not artifact_path.exists():
        raise FileNotFoundError(
            "Recession model not trained. Run: python train_recession.py"
        )

    artifact = joblib.load(artifact_path)
    model = artifact["model"]
    scaler = artifact["scaler"]
    feature_cols = artifact["feature_cols"]

    df = _load_all_series(db_path)
    monthly = _to_monthly_panel(df)
    usrec = monthly.get("USREC", pd.Series(0.0, index=monthly.index))
    usrec = usrec.reindex(monthly.index, method="ffill").fillna(0)

    feats = _build_features(monthly)
    feats["recession_now"] = usrec.reindex(feats.index, method="ffill").fillna(0)
    feats = feats.dropna(subset=feature_cols)

    X_scaled = scaler.transform(feats[feature_cols].values)
    probs = model.predict_proba(X_scaled)[:, 1]

    current_prob = float(probs[-1])

    # Reload OOS metrics from saved artifact if available
    oos = artifact.get("oos_metrics", {})
    feature_importances = artifact.get("feature_importances", [])

    history = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "probability": round(float(probs[i]), 4),
            "recession": int(row["recession_now"]),
        }
        for i, (idx, row) in enumerate(feats.iterrows())
    ]

    current_features = {col: round(float(feats[col].iloc[-1]), 4) for col in feature_cols}

    if current_prob > 0.65:
        signal = "high"
        signal_label = f"High recession risk ({current_prob:.0%}) — yield curve and labour market data signal elevated probability"
    elif current_prob > 0.35:
        signal = "medium"
        signal_label = f"Moderate recession risk ({current_prob:.0%}) — some leading indicators are deteriorating"
    else:
        signal = "low"
        signal_label = f"Low recession risk ({current_prob:.0%}) — leading indicators remain broadly expansionary"

    return {
        "current_probability": round(current_prob, 4),
        "current_date": feats.index[-1].strftime("%Y-%m-%d"),
        "signal": signal,
        "signal_label": signal_label,
        "current_features": current_features,
        "history": history,
        "oos_metrics": oos,
        "feature_importances": feature_importances,
    }
