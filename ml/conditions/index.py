"""
Economic Conditions Index
-------------------------
Five category sub-indices (Growth, Labor, Inflation, Financial Conditions, Housing)
each computed as a weighted average of 10-year rolling z-scores of their constituent
series. Composite = simple average of the five category scores.

Inspired by the Chicago Fed National Activity Index (CFNAI) methodology but uses
a narrower set of FRED series already in the warehouse.
"""

import duckdb
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

# 10-year rolling window for z-score normalisation.
# This means the score reflects "conditions relative to the past decade"
# rather than the full history — important because the inflation and rate
# regimes of the 1970s-80s are structurally different from today.
ROLLING_WINDOW = 120  # months

# Minimum observations before a rolling z-score is emitted
MIN_PERIODS = 36

# Categories: each indicator has a transform, inversion flag, and weight.
# invert=True means higher raw value → worse conditions (e.g., UNRATE, FEDFUNDS, CPI).
CATEGORIES = {
    "Growth": {
        "description": "Output and consumer spending momentum",
        "color": "#16a34a",
        "labels": ["Contracting", "Slowing", "Moderate", "Solid", "Robust"],
        "indicators": [
            {"series": "GDP",   "transform": "yoy", "invert": False, "weight": 1.2,
             "label": "GDP growth (YoY)", "unit": "%"},
            {"series": "RSXFS", "transform": "yoy", "invert": False, "weight": 1.0,
             "label": "Retail Sales (YoY)", "unit": "%"},
        ],
    },
    "Labor Market": {
        "description": "Employment health and payroll momentum",
        "color": "#2563eb",
        "labels": ["Deteriorating", "Weakening", "Balanced", "Healthy", "Strong"],
        "indicators": [
            {"series": "UNRATE", "transform": "level", "invert": True,  "weight": 1.2,
             "label": "Unemployment Rate", "unit": "%"},
            {"series": "PAYEMS", "transform": "yoy",   "invert": False, "weight": 1.0,
             "label": "Payrolls (YoY)", "unit": "%"},
        ],
    },
    "Inflation": {
        "description": "Price pressure relative to the Fed's 2% target",
        "color": "#dc2626",
        "labels": ["Elevated", "Above Target", "Near Target", "Below Target", "Very Low"],
        "indicators": [
            {"series": "CPIAUCSL", "transform": "yoy", "invert": True, "weight": 1.0,
             "label": "CPI Inflation (YoY)", "unit": "%"},
        ],
    },
    "Financial Conditions": {
        "description": "Monetary policy stance and yield curve signal",
        "color": "#d97706",
        "labels": ["Very Tight", "Restrictive", "Neutral", "Accommodative", "Very Loose"],
        "indicators": [
            {"series": "T10Y2Y",   "transform": "level", "invert": False, "weight": 1.5,
             "label": "10Y-2Y Spread", "unit": "pp"},
            {"series": "FEDFUNDS", "transform": "level", "invert": True,  "weight": 0.8,
             "label": "Fed Funds Rate", "unit": "%"},
        ],
    },
    "Housing": {
        "description": "Rate-sensitive leading indicator for real activity",
        "color": "#0891b2",
        "labels": ["Depressed", "Weak", "Moderate", "Solid", "Boom"],
        "indicators": [
            {"series": "HOUST", "transform": "yoy", "invert": False, "weight": 1.0,
             "label": "Housing Starts (YoY)", "unit": "%"},
        ],
    },
}

# Composite headline labels with score thresholds and display color
COMPOSITE_BANDS = [
    (-1.0,  "Contraction",      "#dc2626"),
    (-0.5,  "Slowdown",         "#d97706"),
    (-0.25, "Below Trend",      "#92400e"),
    ( 0.25, "Neutral",          "#6b7280"),
    ( 0.75, "Moderate Growth",  "#16a34a"),
    ( 9999, "Expansion",        "#15803d"),
]

# Category score → label index mapping (0=worst … 4=best)
_BAND_EDGES = [-1.0, -0.3, 0.3, 1.0]


def _label_idx(score: float) -> int:
    for i, edge in enumerate(_BAND_EDGES):
        if score < edge:
            return i
    return 4


def _composite_label_color(score: float):
    for threshold, label, color in COMPOSITE_BANDS:
        if score < threshold:
            return label, color
    return COMPOSITE_BANDS[-1][1], COMPOSITE_BANDS[-1][2]


Z_CLIP = 3.5  # cap individual z-scores so a single COVID shock can't dominate the composite

def _rolling_zscore(s: pd.Series) -> pd.Series:
    mu = s.rolling(ROLLING_WINDOW, min_periods=MIN_PERIODS).mean()
    sd = s.rolling(ROLLING_WINDOW, min_periods=MIN_PERIODS).std()
    z = (s - mu) / sd.replace(0, np.nan)
    return z.clip(-Z_CLIP, Z_CLIP)


def _load_panel(db_path: str) -> pd.DataFrame:
    needed = ["GDP", "RSXFS", "UNRATE", "PAYEMS", "CPIAUCSL", "T10Y2Y", "FEDFUNDS", "HOUST", "USREC"]
    placeholders = ", ".join(f"'{s}'" for s in needed)
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute(f"""
        SELECT series_id, observation_date, value
        FROM raw.economic_indicators
        WHERE series_id IN ({placeholders}) AND value IS NOT NULL
        ORDER BY observation_date
    """).fetchdf()
    con.close()

    df["observation_date"] = pd.to_datetime(df["observation_date"])
    pivot = df.pivot_table(
        index="observation_date", columns="series_id", values="value", aggfunc="mean"
    )
    return pivot.resample("MS").mean().ffill(limit=3)


def _make_stationary(monthly: pd.DataFrame) -> pd.DataFrame:
    """Return stationary versions of all series."""
    out = pd.DataFrame(index=monthly.index)
    for col in ["GDP", "RSXFS", "CPIAUCSL", "HOUST", "PAYEMS"]:
        if col in monthly.columns:
            out[col] = monthly[col].pct_change(12, fill_method=None) * 100
    for col in ["UNRATE", "FEDFUNDS", "T10Y2Y"]:
        if col in monthly.columns:
            out[col] = monthly[col]
    return out


def compute_conditions_index(db_path: str = "./data/warehouse.duckdb") -> dict:
    monthly = _load_panel(db_path)
    stationary = _make_stationary(monthly)
    usrec = monthly.get("USREC", pd.Series(dtype=float))

    # Compute z-scores for every indicator
    zscores: dict[str, pd.Series] = {}
    for cat_cfg in CATEGORIES.values():
        for ind in cat_cfg["indicators"]:
            s = ind["series"]
            if s not in stationary.columns:
                continue
            z = _rolling_zscore(stationary[s])
            zscores[s] = -z if ind["invert"] else z

    # Category scores
    cat_scores: dict[str, pd.Series] = {}
    for cat_name, cat_cfg in CATEGORIES.items():
        parts = []
        weights = []
        for ind in cat_cfg["indicators"]:
            s = ind["series"]
            if s in zscores:
                parts.append(zscores[s] * ind["weight"])
                weights.append(ind["weight"])
        if not parts:
            continue
        total_w = sum(weights)
        combined = parts[0]
        for p in parts[1:]:
            combined = combined.add(p, fill_value=np.nan)
        cat_scores[cat_name] = combined / total_w

    # Composite = simple average of 5 category scores
    if not cat_scores:
        raise ValueError("No category scores could be computed — check that series are ingested")

    cat_df = pd.DataFrame(cat_scores)
    composite = cat_df.mean(axis=1)

    # Historical percentile (since 1990, to avoid sparse early data)
    since_1990 = composite[composite.index >= "1990-01-01"].dropna()
    current_composite = float(composite.dropna().iloc[-1])
    percentile = int(scipy_stats.percentileofscore(since_1990, current_composite, kind="rank"))

    # Build current category snapshots
    current_categories = []
    for cat_name, cat_cfg in CATEGORIES.items():
        if cat_name not in cat_scores:
            continue
        score_series = cat_scores[cat_name].dropna()
        if score_series.empty:
            continue
        cat_score = float(score_series.iloc[-1])
        idx = _label_idx(cat_score)
        label = cat_cfg["labels"][idx]
        color = cat_cfg["color"]

        # Status color based on label index
        if idx <= 1:
            status = "red"
        elif idx == 2:
            status = "yellow"
        else:
            status = "green"

        # Per-indicator current readings
        indicators_out = []
        for ind in cat_cfg["indicators"]:
            s = ind["series"]
            if s not in zscores:
                continue
            z_now = float(zscores[s].dropna().iloc[-1]) if not zscores[s].dropna().empty else None
            raw_now = None
            if s in stationary.columns:
                raw_s = stationary[s].dropna()
                raw_now = round(float(raw_s.iloc[-1]), 2) if not raw_s.empty else None
            indicators_out.append({
                "series": s,
                "label": ind["label"],
                "unit": ind["unit"],
                "z_score": round(z_now, 3) if z_now is not None else None,
                "raw_value": raw_now,
                "invert": ind["invert"],
            })

        # Category percentile
        cat_hist = score_series[score_series.index >= "1990-01-01"]
        cat_pct = int(scipy_stats.percentileofscore(cat_hist, cat_score, kind="rank")) if not cat_hist.empty else None

        current_categories.append({
            "name": cat_name,
            "score": round(cat_score, 3),
            "percentile": cat_pct,
            "label": label,
            "status": status,
            "color": color,
            "description": cat_cfg["description"],
            "indicators": indicators_out,
        })

    # History — monthly, from 1990, for the time series chart
    history_start = "1990-01-01"
    history = []
    for idx in composite.index:
        if str(idx.date()) < history_start or pd.isna(composite[idx]):
            continue
        row: dict = {"date": idx.strftime("%Y-%m-%d"), "composite": round(float(composite[idx]), 3)}
        for cat_name in cat_scores:
            val = cat_scores[cat_name].get(idx, np.nan)
            row[cat_name.lower().replace(" ", "_")] = round(float(val), 3) if not pd.isna(val) else None
        rec = usrec.get(idx, np.nan)
        row["recession"] = int(rec) if not pd.isna(rec) else 0
        history.append(row)

    # Validation: average composite in expansion vs recession
    rec_mask = usrec.reindex(composite.index).fillna(0) == 1
    exp_avg = float(composite[~rec_mask].dropna().mean())
    rec_avg = float(composite[rec_mask].dropna().mean())

    composite_label, composite_color = _composite_label_color(current_composite)

    return {
        "composite": {
            "score": round(current_composite, 3),
            "percentile": percentile,
            "label": composite_label,
            "color": composite_color,
        },
        "categories": current_categories,
        "history": history,
        "validation": {
            "expansion_avg": round(exp_avg, 3),
            "recession_avg": round(rec_avg, 3),
            "separation": round(exp_avg - rec_avg, 3),
        },
    }
