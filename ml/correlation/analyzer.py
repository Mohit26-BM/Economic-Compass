import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import grangercausalitytests

ANALYSIS_SERIES = ["GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS", "T10Y2Y", "HOUST", "RSXFS"]

GRANGER_PAIRS = [
    ("FEDFUNDS", "UNRATE"),
    ("FEDFUNDS", "CPIAUCSL"),
    ("T10Y2Y", "HOUST"),
    ("FEDFUNDS", "HOUST"),
    ("T10Y2Y", "UNRATE"),
    ("CPIAUCSL", "FEDFUNDS"),
]

SCATTER_PAIRS = [
    ("FEDFUNDS", "UNRATE", 9),
    ("T10Y2Y", "HOUST", 12),
    ("FEDFUNDS", "CPIAUCSL", 18),
]


def _make_stationary(monthly: pd.DataFrame) -> pd.DataFrame:
    """
    Convert trending series to stationary growth rates.

    GDP, CPI, RSXFS, HOUST all trend upward over time. Correlating levels
    gives spurious r≈0.98 even between unrelated series (shared trend artifact).
    YoY growth rates are mean-reverting and economically meaningful.
    FEDFUNDS, UNRATE, T10Y2Y are already rate/spread measures — kept as levels.
    """
    out = pd.DataFrame(index=monthly.index)

    if "GDP" in monthly.columns:
        # GDP is quarterly forward-filled; pct_change(12) ≈ YoY growth on monthly data
        out["GDP"] = monthly["GDP"].pct_change(12, fill_method=None) * 100

    if "CPIAUCSL" in monthly.columns:
        out["CPIAUCSL"] = monthly["CPIAUCSL"].pct_change(12, fill_method=None) * 100  # YoY inflation %

    if "RSXFS" in monthly.columns:
        out["RSXFS"] = monthly["RSXFS"].pct_change(12, fill_method=None) * 100  # YoY retail growth %

    if "HOUST" in monthly.columns:
        out["HOUST"] = monthly["HOUST"].pct_change(12, fill_method=None) * 100  # YoY housing starts change %

    for s in ["FEDFUNDS", "UNRATE", "T10Y2Y"]:
        if s in monthly.columns:
            out[s] = monthly[s]

    return out


def _load_monthly_panel(db_path: str = "./data/warehouse.duckdb") -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute("""
        SELECT series_id, observation_date, value
        FROM raw.economic_indicators
        WHERE series_id != 'USREC' AND value IS NOT NULL
        ORDER BY observation_date
    """).fetchdf()
    con.close()

    df["observation_date"] = pd.to_datetime(df["observation_date"])
    pivot = df.pivot_table(
        index="observation_date", columns="series_id", values="value", aggfunc="mean"
    )
    monthly = pivot.resample("MS").mean().ffill(limit=3)
    return monthly


def compute_cross_correlations(monthly: pd.DataFrame, max_lag: int = 12) -> list[dict]:
    """
    Correlate stationary (growth-rate) versions of each series.

    max_lag is intentionally capped at 12 months. Searching over 25 lags × 21 pairs
    = 525 comparisons inflates apparent significance purely by chance. p-values
    reported here are Pearson p at the chosen lag and are NOT corrected for the lag
    search, and YoY growth rates overlap month to month (so the effective sample is far
    smaller than the row count) — treat them as a ranking, not as hypothesis tests.
    """
    transformed = _make_stationary(monthly)
    series = [s for s in ANALYSIS_SERIES if s in transformed.columns]
    results = []

    for i, s1 in enumerate(series):
        for j, s2 in enumerate(series):
            if i >= j:
                continue
            best_corr = 0.0
            best_lag = 0
            best_pval = 1.0
            leader, follower = s1, s2

            # Either series may be the one that leads, so try both directions. (Only testing the
            # first-listed series as leader could never find "the Fed funds rate leads unemployment"
            # once unemployment happened to be listed first.)
            for lead, follow in ((s1, s2), (s2, s1)):
                for lag in range(0, max_lag + 1):
                    if lag == 0 and lead == s2:
                        continue  # lag 0 is symmetric; count it once
                    shifted = transformed[lead].shift(lag)
                    combined = pd.DataFrame({"a": shifted, "b": transformed[follow]}).dropna()
                    if len(combined) < 30:
                        continue
                    r, p = stats.pearsonr(combined["a"], combined["b"])
                    if not np.isnan(r) and abs(r) > abs(best_corr):
                        best_corr, best_lag, best_pval = r, lag, p
                        leader, follower = lead, follow

            results.append({
                "series_a": leader,   # series_a leads series_b by best_lag months
                "series_b": follower,
                "best_lag": best_lag,
                "correlation": round(best_corr, 4),
                "p_value": round(float(best_pval), 6),
                "significant": bool(best_pval < 0.01),  # conservative: 0.01 not 0.05 given lag search
            })

    return results


def _granger_inputs(monthly: pd.DataFrame) -> pd.DataFrame:
    """
    Granger tests are only valid on stationary series. Trending series (CPI, housing) become YoY
    growth; rate and spread series are first-differenced (their levels are close to unit roots).
    The previous version tested raw levels, which produces spurious "causality" from shared trends.
    """
    out = pd.DataFrame(index=monthly.index)
    for s in ("CPIAUCSL", "HOUST", "GDP", "RSXFS"):
        if s in monthly.columns:
            out[s] = monthly[s].pct_change(12, fill_method=None) * 100
    for s in ("FEDFUNDS", "UNRATE", "T10Y2Y"):
        if s in monthly.columns:
            out[s] = monthly[s].diff()
    return out


def run_granger_tests(monthly: pd.DataFrame) -> list[dict]:
    results = []
    monthly = _granger_inputs(monthly)

    for cause, effect in GRANGER_PAIRS:
        if cause not in monthly.columns or effect not in monthly.columns:
            continue
        data = monthly[[effect, cause]].dropna()
        if len(data) < 60:
            continue
        try:
            test_result = grangercausalitytests(data, maxlag=6)
            best_lag = min(
                test_result.keys(),
                key=lambda k: test_result[k][0]["ssr_ftest"][1],
            )
            best_p = float(test_result[best_lag][0]["ssr_ftest"][1])
            # We looked at 6 lags and pick the best, so the honest p-value is larger. Bonferroni.
            best_p = min(1.0, best_p * 6)

            if best_p < 0.05:
                interp = (
                    f"Changes in {cause} statistically predict changes in {effect} "
                    f"with ~{best_lag}-month lag (p={best_p:.3f})"
                )
            else:
                interp = f"No significant Granger-causal relationship found (p={best_p:.3f})"

            results.append({
                "cause": cause,
                "effect": effect,
                "best_lag": int(best_lag),
                "p_value": round(float(best_p), 6),
                "significant": bool(best_p < 0.05),
                "interpretation": interp,
            })
        except Exception:
            pass

    return results


def get_scatter_pairs(monthly: pd.DataFrame) -> list[dict]:
    transformed = _make_stationary(monthly)
    results = []

    for cause, effect, lag in SCATTER_PAIRS:
        if cause not in transformed.columns or effect not in transformed.columns:
            continue
        data = pd.DataFrame({
            "x": transformed[cause].shift(lag),
            "y": transformed[effect],
        }).dropna()
        if len(data) < 20:
            continue

        r, p = stats.pearsonr(data["x"], data["y"])
        r_sq = r ** 2

        # Human-readable axis labels reflect the transformation applied
        x_label = cause if cause in ("FEDFUNDS", "UNRATE", "T10Y2Y") else f"{cause} YoY%"
        y_label = effect if effect in ("FEDFUNDS", "UNRATE", "T10Y2Y") else f"{effect} YoY%"

        results.append({
            "cause": cause,
            "effect": effect,
            "lag": lag,
            "label": f"{cause}[t−{lag}mo] vs {effect}[t]",
            "x_label": f"{x_label} (t−{lag}mo)",
            "y_label": y_label,
            "pearson_r": round(float(r), 4),
            "r_squared": round(float(r_sq), 4),
            "p_value": round(float(p), 6),
            "n": len(data),
            "data": [
                {"x": round(float(row["x"]), 4), "y": round(float(row["y"]), 4)}
                for _, row in data.iterrows()
            ],
        })

    return results


def run_full_analysis(db_path: str = "./data/warehouse.duckdb") -> dict:
    monthly = _load_monthly_panel(db_path)
    cross_correlations = compute_cross_correlations(monthly)
    granger = run_granger_tests(monthly)
    scatter = get_scatter_pairs(monthly)

    return {
        "series": [s for s in ANALYSIS_SERIES if s in monthly.columns],
        "cross_correlations": cross_correlations,
        "granger_results": granger,
        "scatter_pairs": scatter,
    }
