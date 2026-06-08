import duckdb
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

# Features are rates of change, not levels.
# Levels create "era" clusters (1970s ≈ 2022 because both have high nominal CPI).
# Change features capture economic dynamics: acceleration, contraction, pivot.
REGIME_COLORS = {
    "Expansion": "#16a34a",
    "Tightening": "#d97706",
    "Recession": "#dc2626",
    "Recovery": "#2563eb",
    "Crisis":    "#7c3aed",  # extreme shock cluster (e.g. COVID collapse)
}


def _load_monthly_panel(db_path: str = "./data/warehouse.duckdb") -> pd.DataFrame:
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


def _build_regime_features(monthly: pd.DataFrame) -> pd.DataFrame:
    """
    Replace raw levels with regime-sensitive features.

    Using levels clusters on historical price levels (1970s ≈ 2022 = both
    have "high CPI") rather than on economic dynamics. Change/growth features
    capture what actually distinguishes regimes: acceleration, contraction, pivot.
    """
    feats = pd.DataFrame(index=monthly.index)

    if "CPIAUCSL" in monthly.columns:
        feats["CPI_yoy"] = monthly["CPIAUCSL"].pct_change(12) * 100

    if "GDP" in monthly.columns:
        # GDP is quarterly — forward-filled, so pct_change(4) ≈ annual growth.
        # fill_method=None avoids the pandas 2.2 deprecation warning; the monthly
        # panel is already ffill-ed upstream so NaNs here are genuine gaps.
        feats["GDP_growth"] = monthly["GDP"].pct_change(4, fill_method=None) * 100

    if "RSXFS" in monthly.columns:
        feats["RSXFS_yoy"] = monthly["RSXFS"].pct_change(12) * 100

    if "HOUST" in monthly.columns:
        feats["HOUST_yoy"] = monthly["HOUST"].pct_change(12) * 100

    if "UNRATE" in monthly.columns:
        # Level AND 3-month change — captures both current slack and acceleration
        feats["UNRATE"] = monthly["UNRATE"]
        feats["UNRATE_3m_chg"] = monthly["UNRATE"].diff(3)

    if "FEDFUNDS" in monthly.columns:
        # Level captures policy stance; 12m change captures hiking/cutting cycle
        feats["FEDFUNDS"] = monthly["FEDFUNDS"]
        feats["FEDFUNDS_12m_chg"] = monthly["FEDFUNDS"].diff(12)

    if "T10Y2Y" in monthly.columns:
        # Already a spread (relative measure) — level is appropriate
        feats["T10Y2Y"] = monthly["T10Y2Y"]

    return feats


def _label_regimes(
    centers: pd.DataFrame,
    usrec_by_cluster: dict[int, float] | None = None,
) -> dict[int, str]:
    """
    Assign regime labels to clusters.

    When USREC overlap rates are provided (usrec_by_cluster), we use them directly
    to identify the recession cluster — this is more reliable than scoring because
    it sidesteps outlier clusters (e.g. 2-3 COVID-shock months that score extremely
    high on every recession signal but represent a tiny fraction of actual recessions).

    The remaining three labels (Tightening, Expansion, Recovery) are assigned by
    multi-feature scoring on z-scored centroids.
    """
    ids = list(centers.index)
    labels: dict[int, str] = {}

    def score(candidates: list, contributions: dict) -> int:
        s = pd.Series(0.0, index=candidates)
        for col, sign in contributions.items():
            if col in centers.columns:
                s += sign * centers.loc[candidates, col]
        return int(s.idxmax())

    # Recession: use USREC overlap when available (highest P(USREC=1 | cluster))
    if usrec_by_cluster:
        rec_id = max(ids, key=lambda i: usrec_by_cluster.get(i, 0.0))
    else:
        # Fall back to scoring — note: may mis-assign if outlier clusters exist
        rec_id = score(ids, {
            "UNRATE_3m_chg": +1.5,
            "GDP_growth":    -1.0,
            "RSXFS_yoy":     -1.0,
            "HOUST_yoy":     -0.8,
            "T10Y2Y":        -0.5,
            "UNRATE":        +0.5,
        })
    labels[rec_id] = "Recession"
    ids.remove(rec_id)

    # Tightening: rising rates, elevated inflation, Fed actively hiking
    tight_id = score(ids, {
        "FEDFUNDS_12m_chg": +1.5,
        "FEDFUNDS":         +1.0,
        "CPI_yoy":          +0.8,
        "UNRATE_3m_chg":    -0.5,
    })
    labels[tight_id] = "Tightening"
    ids.remove(tight_id)

    # Expansion: strong growth, unemployment stable or falling, healthy consumer
    if len(ids) >= 2:
        exp_id = score(ids, {
            "GDP_growth":    +1.0,
            "RSXFS_yoy":     +1.0,
            "UNRATE_3m_chg": -1.0,
            "HOUST_yoy":     +0.5,
        })
        labels[exp_id] = "Expansion"
        ids.remove(exp_id)

    # Remaining cluster: Recovery (normal post-recession rebound) or Crisis
    # (extreme outlier like COVID collapse). Distinguish by UNRATE_3m_chg z-score:
    # a genuine crisis has unemployment spiking several standard deviations.
    for r in ids:
        unrate_z = float(centers.loc[r, "UNRATE_3m_chg"]) if "UNRATE_3m_chg" in centers.columns else 0.0
        labels[r] = "Crisis" if unrate_z > 2.5 else "Recovery"

    return labels


def _usrec_cross_tab(data: pd.DataFrame, monthly: pd.DataFrame) -> dict:
    """Validate regime labels against NBER recession indicator."""
    if "USREC" not in monthly.columns:
        return {}

    usrec = monthly["USREC"].reindex(data.index, method="ffill").fillna(0)
    data = data.copy()
    data["usrec"] = usrec

    validation = {}
    for regime in data["regime"].unique():
        mask = data["regime"] == regime
        total = int(mask.sum())
        rec = int(data.loc[mask, "usrec"].sum())
        rate = round(rec / total, 4) if total > 0 else 0.0

        # Is the recession rate consistent with the label?
        # For clusters with fewer than 12 months the sample is too small for strict
        # thresholds — a single mis-classified month can swing the rate significantly.
        if total < 12:
            valid = True  # too few months for reliable rate estimation
        elif regime == "Recession":
            valid = rate >= 0.50
        elif regime in ("Expansion", "Tightening"):
            valid = rate <= 0.25
        elif regime == "Crisis":
            valid = rate >= 0.30  # crisis months should be mostly real recessions
        else:  # Recovery
            valid = rate <= 0.30

        validation[regime] = {
            "total_months": total,
            "recession_months": rec,
            "recession_rate": rate,
            "label_valid": valid,
        }

    return validation


def detect_regimes(db_path: str = "./data/warehouse.duckdb", n_clusters: int = 4) -> dict:
    monthly = _load_monthly_panel(db_path)
    feats = _build_regime_features(monthly)
    data = feats.dropna()

    if len(data) < 50:
        raise ValueError("Insufficient aligned data for regime detection")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(data.values)

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=20)
    labels_arr = km.fit_predict(X_scaled)

    sil = float(round(silhouette_score(X_scaled, labels_arr), 4))

    centers_scaled = pd.DataFrame(km.cluster_centers_, columns=data.columns)
    # Original-unit centroids let the UI show "GDP growth: -2.1%" instead of "-1.5σ"
    centers_original = pd.DataFrame(
        scaler.inverse_transform(km.cluster_centers_), columns=data.columns
    )

    # Compute P(USREC=1 | cluster) before labeling so the recession cluster
    # is identified by actual NBER overlap, not by scoring. This avoids
    # mis-labeling extreme outlier clusters (e.g. 2-3 COVID months that score
    # highest on every recession signal yet represent a tiny slice of recessions).
    data = data.copy()
    data["cluster"] = labels_arr
    usrec_by_cluster: dict[int, float] | None = None
    if "USREC" in monthly.columns:
        usrec_s = monthly["USREC"].reindex(data.index, method="ffill").fillna(0)
        usrec_by_cluster = {
            int(c): float(usrec_s[data["cluster"] == c].mean())
            for c in range(n_clusters)
        }

    regime_map = _label_regimes(centers_scaled, usrec_by_cluster=usrec_by_cluster)
    data["regime"] = data["cluster"].map(regime_map)

    current_regime = str(data["regime"].iloc[-1])
    current_date = data.index[-1].strftime("%Y-%m-%d")

    timeline = [
        {"date": idx.strftime("%Y-%m-%d"), "regime": row["regime"], "cluster": int(row["cluster"])}
        for idx, row in data.iterrows()
    ]

    # Units and formatting for original-unit centroid display
    FEATURE_FORMAT = {
        "CPI_yoy":          {"label": "CPI YoY",          "unit": "%",  "decimals": 1},
        "GDP_growth":       {"label": "GDP Growth",        "unit": "%",  "decimals": 1},
        "RSXFS_yoy":        {"label": "Retail Sales YoY",  "unit": "%",  "decimals": 1},
        "HOUST_yoy":        {"label": "Housing Starts YoY","unit": "%",  "decimals": 1},
        "UNRATE":           {"label": "Unemployment",      "unit": "%",  "decimals": 1},
        "UNRATE_3m_chg":    {"label": "UNRATE 3m chg",     "unit": "pp", "decimals": 2},
        "FEDFUNDS":         {"label": "Fed Funds",         "unit": "%",  "decimals": 1},
        "FEDFUNDS_12m_chg": {"label": "Fed Funds 12m chg", "unit": "pp", "decimals": 2},
        "T10Y2Y":           {"label": "10Y-2Y Spread",     "unit": "%",  "decimals": 2},
    }

    profiles = []
    for cluster_id, regime_name in regime_map.items():
        mask = data["cluster"] == cluster_id
        center_z = centers_scaled.loc[cluster_id]
        center_raw = centers_original.loc[cluster_id]

        raw_stats = {}
        for col in data.columns:
            if col in ("cluster", "regime"):
                continue
            fmt = FEATURE_FORMAT.get(col, {"label": col, "unit": "", "decimals": 2})
            raw_stats[col] = {
                "label": fmt["label"],
                "value": round(float(center_raw[col]), fmt["decimals"]),
                "unit": fmt["unit"],
            }

        profiles.append({
            "id": cluster_id,
            "name": regime_name,
            "color": REGIME_COLORS.get(regime_name, "#6b7280"),
            "features": {col: round(float(center_z[col]), 3) for col in data.columns if col not in ("cluster", "regime")},
            "centroid": raw_stats,
            "count": int(mask.sum()),
        })

    radar_data = []
    feature_cols = [c for c in data.columns if c not in ("cluster", "regime")]
    for col in feature_cols:
        row: dict = {"series": col}
        for p in profiles:
            row[p["name"]] = p["features"].get(col, 0)
        radar_data.append(row)

    recent_year = data.index[-1].year
    same_regime_years = (
        data[data["regime"] == current_regime]
        .resample("YS").first().index.year.tolist()
    )
    analogues = [y for y in same_regime_years if y < recent_year - 2][-5:]

    usrec_validation = _usrec_cross_tab(data, monthly)

    return {
        "current_regime": current_regime,
        "current_date": current_date,
        "color": REGIME_COLORS.get(current_regime, "#6b7280"),
        "profiles": profiles,
        "radar_data": radar_data,
        "timeline": timeline,
        "historical_analogues": analogues,
        "regime_colors": REGIME_COLORS,
        "silhouette_score": sil,
        "silhouette_interpretation": (
            "Strong separation" if sil > 0.5
            else "Reasonable separation" if sil > 0.25
            else "Weak separation — regimes may overlap significantly"
        ),
        "usrec_validation": usrec_validation,
        "feature_set": "change/growth rates (not levels)",
    }
