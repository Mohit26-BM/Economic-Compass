"""
Economic Scenario Simulator
----------------------------
Given a hypothetical set of indicator values, compute what each model would say:
  - Taylor Rule prescribed rate and policy gap
  - Logistic regression recession probability
  - Conditions Index composite score and category scores
  - Nearest historical analogues (Euclidean distance on z-scores)
  - Rule-based regime label

The recession model is loaded from the trained artifact; all other outputs are
computed analytically from the user's inputs against the historical z-score baseline.
"""

from pathlib import Path
import os

import duckdb
import joblib
import numpy as np
import pandas as pd

ARTIFACTS = Path(os.environ.get("MODEL_ARTIFACTS_PATH", "./ml/artifacts"))
ROLLING_WINDOW = 120  # 10-year z-score window (same as conditions index)
MIN_PERIODS = 36

# Taylor Rule constants
NEUTRAL_RATE = 2.0
INFLATION_TARGET = 2.0
POTENTIAL_GDP_GROWTH = 2.5  # simplified; HP-filter not available for single point

# Slider range definitions surfaced to the UI
SLIDER_CONFIG = {
    "fedfunds":   {"label": "Fed Funds Rate",        "unit": "%",  "min": 0.0,  "max": 10.0, "step": 0.25},
    "cpi_yoy":    {"label": "CPI Inflation (YoY)",   "unit": "%",  "min": -2.0, "max": 12.0, "step": 0.1},
    "gdp_yoy":    {"label": "GDP Growth (YoY)",      "unit": "%",  "min": -8.0, "max": 10.0, "step": 0.1},
    "unrate":     {"label": "Unemployment Rate",     "unit": "%",  "min": 2.0,  "max": 12.0, "step": 0.1},
    "t10y2y":     {"label": "10Y–2Y Spread",         "unit": "pp", "min": -3.0, "max": 3.5,  "step": 0.05},
    "houst_yoy":  {"label": "Housing Starts (YoY)",  "unit": "%",  "min":-50.0, "max": 60.0, "step": 1.0},
    "rsxfs_yoy":  {"label": "Retail Sales (YoY)",    "unit": "%",  "min":-15.0, "max": 20.0, "step": 0.5},
}


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_monthly(db_path: str) -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute("""
        SELECT series_id, observation_date, value
        FROM raw.economic_indicators
        WHERE value IS NOT NULL
        ORDER BY observation_date
    """).fetchdf()
    con.close()

    df["observation_date"] = pd.to_datetime(df["observation_date"])
    pivot = df.pivot_table(
        index="observation_date", columns="series_id", values="value", aggfunc="mean"
    )
    return pivot.resample("MS").mean().ffill(limit=3)


def _make_stationary(monthly: pd.DataFrame) -> pd.DataFrame:
    """Stationary transforms — YoY for trending series, level for rates."""
    out = pd.DataFrame(index=monthly.index)
    for col in ["GDP", "RSXFS", "CPIAUCSL", "HOUST", "PAYEMS"]:
        if col in monthly.columns:
            out[col] = monthly[col].pct_change(12, fill_method=None) * 100
    for col in ["UNRATE", "FEDFUNDS", "T10Y2Y"]:
        if col in monthly.columns:
            out[col] = monthly[col]
    return out


# ---------------------------------------------------------------------------
# Taylor Rule
# ---------------------------------------------------------------------------

def _compute_taylor(inputs: dict) -> dict:
    fedfunds  = inputs["fedfunds"]
    cpi_yoy   = inputs["cpi_yoy"]
    gdp_yoy   = inputs["gdp_yoy"]

    pi_gap      = cpi_yoy - INFLATION_TARGET
    output_gap  = gdp_yoy - POTENTIAL_GDP_GROWTH
    taylor_rate = NEUTRAL_RATE + cpi_yoy + 0.5 * pi_gap + 0.5 * output_gap
    policy_gap  = fedfunds - taylor_rate

    if policy_gap > 1.0:
        signal = "tight"
        explanation = (
            f"Actual rate is {policy_gap:.1f}pp above the Taylor prescription. "
            "Policy is restrictive relative to current inflation and growth."
        )
    elif policy_gap < -1.0:
        signal = "loose"
        explanation = (
            f"Actual rate is {abs(policy_gap):.1f}pp below the Taylor prescription. "
            "Policy is accommodative relative to current inflation and growth."
        )
    else:
        signal = "neutral"
        explanation = (
            f"Actual rate is within 1pp of the Taylor prescription ({taylor_rate:.1f}%). "
            "Policy is roughly neutral."
        )

    return {
        "taylor_rate": round(taylor_rate, 2),
        "actual_rate": round(fedfunds, 2),
        "policy_gap":  round(policy_gap, 2),
        "pi_gap":      round(pi_gap, 2),
        "output_gap":  round(output_gap, 2),
        "signal":      signal,
        "explanation": explanation,
        "note": "Output gap uses simplified GDP − 2.5% approximation (HP filter requires a full series)",
    }


# ---------------------------------------------------------------------------
# Recession probability — load trained model, override level features
# ---------------------------------------------------------------------------

def _compute_recession(inputs: dict, db_path: str) -> dict:
    artifact_path = ARTIFACTS / "recession_model.joblib"
    if not artifact_path.exists():
        return {"probability": None, "signal": "unknown",
                "explanation": "Recession model not trained — run train_recession.py"}

    artifact  = joblib.load(artifact_path)
    model     = artifact["model"]
    scaler    = artifact["scaler"]
    feature_cols = artifact["feature_cols"]

    # Build the full feature matrix from history so momentum features are real
    monthly = _load_monthly(db_path)
    from ml.recession.model import _build_features
    feats = _build_features(monthly).dropna(subset=feature_cols)

    row = feats[feature_cols].iloc[-1].copy()

    # Override the level (spot) features the user has set
    override_map = {
        "t10y2y":   inputs.get("t10y2y"),
        "unrate":   inputs.get("unrate"),
        "fedfunds": inputs.get("fedfunds"),
        "cpi_yoy":  inputs.get("cpi_yoy"),
        "gdp_yoy":  inputs.get("gdp_yoy"),
    }
    for col, val in override_map.items():
        if col in row.index and val is not None:
            row[col] = float(val)

    X_scaled = scaler.transform(row.values.reshape(1, -1))
    prob = float(model.predict_proba(X_scaled)[0, 1])

    # Build plain-English explanation from inputs
    reasons = []
    t10y2y = inputs.get("t10y2y", 0.0)
    unrate  = inputs.get("unrate", 4.0)
    fedfunds = inputs.get("fedfunds", 4.0)
    if t10y2y < 0:
        reasons.append(f"yield curve inverted ({t10y2y:+.2f}pp) — historically precedes recession")
    elif t10y2y > 1.0:
        reasons.append(f"yield curve steep ({t10y2y:+.2f}pp) — historically expansionary signal")
    if unrate > 5.5:
        reasons.append(f"unemployment elevated ({unrate:.1f}%)")
    elif unrate < 4.0:
        reasons.append(f"unemployment low ({unrate:.1f}%) — labour market tight")
    if fedfunds > 5.0:
        reasons.append(f"rates restrictive ({fedfunds:.1f}%)")

    signal = "high" if prob > 0.65 else "medium" if prob > 0.35 else "low"
    signal_color = {"high": "#dc2626", "medium": "#d97706", "low": "#16a34a"}[signal]

    return {
        "probability": round(prob, 4),
        "signal":      signal,
        "signal_color": signal_color,
        "explanation": ". ".join(reasons) if reasons else "No strong recession signals from these inputs.",
        "note": "Momentum features (3m/6m/12m changes) use current historical values; only level inputs are overridden.",
    }


# ---------------------------------------------------------------------------
# Conditions Index — z-score inputs against historical baseline
# ---------------------------------------------------------------------------

def _compute_conditions(inputs: dict, db_path: str) -> dict:
    monthly    = _load_monthly(db_path)
    stationary = _make_stationary(monthly)

    # Map user inputs to stationary series keys
    input_map = {
        "FEDFUNDS": inputs.get("fedfunds"),
        "CPIAUCSL": inputs.get("cpi_yoy"),
        "GDP":      inputs.get("gdp_yoy"),
        "UNRATE":   inputs.get("unrate"),
        "T10Y2Y":   inputs.get("t10y2y"),
        "HOUST":    inputs.get("houst_yoy"),
        "RSXFS":    inputs.get("rsxfs_yoy"),
    }

    from ml.conditions.index import CATEGORIES, _rolling_zscore, _composite_label_color, _label_idx

    # Compute z-score normalisation params from full history for each series
    z_params: dict[str, tuple[float, float]] = {}
    for col in stationary.columns:
        s = stationary[col].dropna()
        mu = s.rolling(ROLLING_WINDOW, min_periods=MIN_PERIODS).mean()
        sd = s.rolling(ROLLING_WINDOW, min_periods=MIN_PERIODS).std()
        if not mu.dropna().empty:
            z_params[col] = (float(mu.dropna().iloc[-1]), float(sd.dropna().iloc[-1]))

    def zscore_input(series_key: str, val: float, invert: bool) -> float | None:
        if series_key not in z_params:
            return None
        mu, sd = z_params[series_key]
        if sd < 1e-10:
            return None
        z = (val - mu) / sd
        z = max(-3.5, min(3.5, z))
        return -z if invert else z

    # Build category scores
    category_results = []
    cat_scores = []

    for cat_name, cat_cfg in CATEGORIES.items():
        parts, weights = [], []
        indicators_out = []
        for ind in cat_cfg["indicators"]:
            s = ind["series"]
            val = input_map.get(s)
            if val is None:
                continue
            z = zscore_input(s, val, ind["invert"])
            if z is None:
                continue
            parts.append(z * ind["weight"])
            weights.append(ind["weight"])
            indicators_out.append({
                "series": s,
                "label": ind["label"],
                "raw_value": round(val, 2),
                "unit": ind["unit"],
                "z_score": round(z, 3),
            })
        if not parts:
            continue
        cat_score = sum(parts) / sum(weights)
        cat_scores.append(cat_score)

        idx = _label_idx(cat_score)
        label = cat_cfg["labels"][idx]
        status = "green" if idx >= 3 else "yellow" if idx == 2 else "red"

        category_results.append({
            "name":        cat_name,
            "score":       round(cat_score, 3),
            "label":       label,
            "status":      status,
            "color":       cat_cfg["color"],
            "indicators":  indicators_out,
        })

    composite = round(float(np.mean(cat_scores)), 3) if cat_scores else 0.0
    label, color = _composite_label_color(composite)

    return {
        "composite": {"score": composite, "label": label, "color": color},
        "categories": category_results,
    }


# ---------------------------------------------------------------------------
# Historical analogues — top-N closest periods by Euclidean distance on z-scores
# ---------------------------------------------------------------------------

def _find_analogues(inputs: dict, db_path: str, n: int = 5) -> list[dict]:
    monthly    = _load_monthly(db_path)
    stationary = _make_stationary(monthly)

    # Same series set used in conditions index
    series_keys = list(stationary.columns)

    # Build full z-score history
    z_history = pd.DataFrame(index=stationary.index)
    for col in series_keys:
        s = stationary[col]
        mu = s.rolling(ROLLING_WINDOW, min_periods=MIN_PERIODS).mean()
        sd = s.rolling(ROLLING_WINDOW, min_periods=MIN_PERIODS).std()
        z_history[col] = (s - mu) / sd.replace(0, np.nan)

    z_history = z_history.dropna()

    # Build the query vector from user inputs
    input_map = {
        "FEDFUNDS": inputs.get("fedfunds"),
        "CPIAUCSL": inputs.get("cpi_yoy"),
        "GDP":      inputs.get("gdp_yoy"),
        "UNRATE":   inputs.get("unrate"),
        "T10Y2Y":   inputs.get("t10y2y"),
        "HOUST":    inputs.get("houst_yoy"),
        "RSXFS":    inputs.get("rsxfs_yoy"),
    }

    # Use z_params from the latest rolling window
    z_latest = z_history.iloc[-1].copy()
    query = []
    cols_used = []
    for col in z_history.columns:
        val = input_map.get(col)
        if val is None:
            query.append(float(z_latest[col]) if not np.isnan(z_latest[col]) else 0.0)
        else:
            # z-score the user's input using current window params
            s = stationary[col].dropna()
            mu_s = s.rolling(ROLLING_WINDOW, min_periods=MIN_PERIODS).mean().dropna()
            sd_s = s.rolling(ROLLING_WINDOW, min_periods=MIN_PERIODS).std().dropna()
            if len(mu_s) and sd_s.iloc[-1] > 1e-10:
                query.append(float((val - mu_s.iloc[-1]) / sd_s.iloc[-1]))
            else:
                query.append(0.0)
        cols_used.append(col)

    query_vec = np.array(query)
    hist_mat  = z_history[cols_used].values

    distances = np.sqrt(((hist_mat - query_vec) ** 2).sum(axis=1))

    # Exclude the most recent 12 months from analogues
    cutoff_idx = len(z_history) - 12
    distances[:max(0, cutoff_idx - cutoff_idx)] = np.nan  # don't exclude older
    if cutoff_idx > 0:
        distances[cutoff_idx:] = np.nan  # mask recent period

    # Load regime labels for context
    try:
        from ml.regime.detector import detect_regimes
        regime_data = detect_regimes(db_path)
        regime_map = {r["date"]: r["regime"] for r in regime_data["timeline"]}
    except Exception:
        regime_map = {}

    valid_mask = ~np.isnan(distances)
    sorted_idx = np.argsort(np.where(valid_mask, distances, np.inf))

    results = []
    seen_years = set()
    for i in sorted_idx:
        if len(results) >= n:
            break
        if not valid_mask[i]:
            continue
        dt = z_history.index[i]
        year = dt.year
        # Avoid showing two months from the same year
        if year in seen_years:
            continue
        seen_years.add(year)
        date_str = dt.strftime("%Y-%m-%d")
        results.append({
            "date":     date_str,
            "year":     year,
            "distance": round(float(distances[i]), 3),
            "regime":   regime_map.get(date_str, "—"),
            "values": {
                col: round(float(stationary[col].get(dt, np.nan)), 2)
                for col in series_keys if col in stationary.columns and not np.isnan(stationary[col].get(dt, np.nan))
            },
        })

    return results


# ---------------------------------------------------------------------------
# Rule-based regime label (for the simulator — no K-means retraining needed)
# ---------------------------------------------------------------------------

def _classify_regime(inputs: dict) -> dict:
    t10y2y   = inputs.get("t10y2y", 0.0)
    unrate   = inputs.get("unrate", 4.5)
    fedfunds = inputs.get("fedfunds", 4.0)
    cpi_yoy  = inputs.get("cpi_yoy", 3.0)
    gdp_yoy  = inputs.get("gdp_yoy", 2.5)
    rsxfs_yoy = inputs.get("rsxfs_yoy", 3.0)

    # Tightening: two distinct cases —
    #   (a) elevated inflation + active hiking
    #   (b) overtightening: rates high AND yield curve inverted (market pricing cuts ahead)
    if (cpi_yoy > 4.0 and fedfunds > 3.0) or (fedfunds > 5.0 and t10y2y < 0):
        reason = (
            "Elevated inflation with restrictive policy stance"
            if cpi_yoy > 4.0
            else f"Overtightening — rate ({fedfunds:.1f}%) well above neutral with yield curve inverted"
        )
        return {"regime": "Tightening", "color": "#d97706", "reason": reason}

    # Recession: weak growth + rising unemployment + inverted curve
    recession_signals = sum([
        gdp_yoy < 0.5,
        t10y2y < -0.5,
        unrate > 5.5,
        rsxfs_yoy < 0,
    ])
    if recession_signals >= 3:
        return {"regime": "Recession", "color": "#dc2626",
                "reason": f"{recession_signals}/4 recession signals active"}

    # Expansion: strong growth, low unemployment, healthy consumer
    if gdp_yoy > 2.5 and unrate < 4.5 and rsxfs_yoy > 2.0 and cpi_yoy <= 4.0:
        return {"regime": "Expansion", "color": "#16a34a",
                "reason": "Strong growth, healthy labour market, contained inflation"}

    # Recovery: positive growth, elevated unemployment, rates not restrictive
    if gdp_yoy > 0 and unrate > 4.5 and fedfunds <= 5.5:
        return {"regime": "Recovery", "color": "#2563eb",
                "reason": "Growth positive but labour market still healing"}

    return {"regime": "Balanced", "color": "#6b7280",
            "reason": "Mixed signals — no dominant regime"}


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def get_defaults(db_path: str) -> dict:
    """Return current real values as slider defaults."""
    monthly = _load_monthly(db_path)
    stat    = _make_stationary(monthly)

    def latest(series_key: str, df: pd.DataFrame) -> float | None:
        s = df[series_key].dropna() if series_key in df.columns else pd.Series()
        return round(float(s.iloc[-1]), 2) if len(s) else None

    return {
        "fedfunds":  latest("FEDFUNDS", monthly),
        "cpi_yoy":   latest("CPIAUCSL", stat),
        "gdp_yoy":   latest("GDP", stat),
        "unrate":    latest("UNRATE", monthly),
        "t10y2y":    latest("T10Y2Y", monthly),
        "houst_yoy": latest("HOUST", stat),
        "rsxfs_yoy": latest("RSXFS", stat),
        "slider_config": SLIDER_CONFIG,
    }


def simulate(inputs: dict, db_path: str) -> dict:
    """Run all models against the hypothetical input vector."""
    taylor     = _compute_taylor(inputs)
    recession  = _compute_recession(inputs, db_path)
    conditions = _compute_conditions(inputs, db_path)
    regime     = _classify_regime(inputs)
    analogues  = _find_analogues(inputs, db_path, n=5)

    return {
        "inputs":     inputs,
        "taylor":     taylor,
        "recession":  recession,
        "conditions": conditions,
        "regime":     regime,
        "analogues":  analogues,
    }
