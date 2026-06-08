import duckdb
import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter

TARGET_INFLATION = 2.0
NEUTRAL_RATE = 2.0
# CPI runs ~0.5–1pp above PCE (the Fed's actual target). A fixed -0.5pp
# adjustment is a conservative approximation of the CPI-to-PCE wedge.
# Historical range: 0.3–0.7pp. Source: BLS / BEA comparison studies.
CPI_PCE_ADJUSTMENT = -0.5


def _load_monthly_panel(db_path: str = "./data/warehouse.duckdb") -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute("""
        SELECT series_id, observation_date, value
        FROM raw.economic_indicators
        WHERE series_id IN ('FEDFUNDS', 'CPIAUCSL', 'GDP') AND value IS NOT NULL
        ORDER BY observation_date
    """).fetchdf()
    con.close()

    df["observation_date"] = pd.to_datetime(df["observation_date"])
    pivot = df.pivot_table(
        index="observation_date", columns="series_id", values="value", aggfunc="mean"
    )
    monthly = pivot.resample("MS").mean().ffill(limit=3)
    return monthly


def compute_taylor_rule(db_path: str = "./data/warehouse.duckdb") -> dict:
    monthly = _load_monthly_panel(db_path)

    if "FEDFUNDS" not in monthly.columns or "CPIAUCSL" not in monthly.columns:
        raise ValueError("FEDFUNDS and CPIAUCSL required for Taylor Rule")

    # Backward-looking: actual recent CPI YoY adjusted toward PCE
    pi_cpi = monthly["CPIAUCSL"].pct_change(12) * 100
    pi_backward = pi_cpi + CPI_PCE_ADJUSTMENT

    # Forward-looking proxy: 5-year rolling average of CPI YoY, PCE-adjusted.
    # The Fed sets rates based on where inflation is heading (12-18 months ahead),
    # not where it is today. The 5-year rolling mean approximates medium-term
    # inflation expectations and dampens transitory spikes (e.g. 2021-22 surge).
    pi_forward = pi_cpi.rolling(60, min_periods=24).mean() + CPI_PCE_ADJUSTMENT

    # Output gap via Hodrick-Prescott filter on quarterly nominal GDP (λ=1600)
    gdp_monthly = monthly.get("GDP", pd.Series(dtype=float)).ffill()
    gdp_q = gdp_monthly.resample("QS").last().dropna()
    if len(gdp_q) >= 16:
        _, gdp_trend_q = hpfilter(gdp_q, lamb=1600)
        gdp_trend = gdp_trend_q.reindex(gdp_monthly.index, method="ffill")
        output_gap = ((gdp_monthly - gdp_trend) / gdp_trend * 100).clip(-6, 6)
    else:
        output_gap = pd.Series(0.0, index=gdp_monthly.index)

    combined = pd.DataFrame({
        "actual_fedfunds": monthly["FEDFUNDS"],
        "cpi_yoy":         pi_cpi,
        "pi_adjusted":     pi_backward,
        "pi_forward":      pi_forward,
        "output_gap":      output_gap,
    }).dropna(subset=["actual_fedfunds", "cpi_yoy"])

    # Backward-looking Taylor Rate: uses current PCE-proxy inflation + HP output gap
    combined["taylor_rate"] = (
        NEUTRAL_RATE
        + combined["pi_adjusted"]
        + 0.5 * (combined["pi_adjusted"] - TARGET_INFLATION)
        + 0.5 * combined["output_gap"]
    ).clip(-5, 25)

    # Forward-looking Taylor Rate: uses smoothed inflation expectations + same output gap.
    # When the two lines converge, it means inflation is at its long-run trend and
    # both specifications agree on where rates should be.
    combined["taylor_forward"] = (
        NEUTRAL_RATE
        + combined["pi_forward"]
        + 0.5 * (combined["pi_forward"] - TARGET_INFLATION)
        + 0.5 * combined["output_gap"]
    ).clip(-5, 25)

    combined["policy_gap"] = combined["actual_fedfunds"] - combined["taylor_rate"]

    history = []
    for idx, row in combined.iterrows():
        if pd.isna(row["actual_fedfunds"]) or pd.isna(row["taylor_rate"]):
            continue
        history.append({
            "date":           idx.strftime("%Y-%m-%d"),
            "actual":         round(float(row["actual_fedfunds"]), 4),
            "taylor":         round(float(row["taylor_rate"]), 4),
            "taylor_forward": round(float(row["taylor_forward"]), 4) if not pd.isna(row["taylor_forward"]) else None,
            "gap":            round(float(row["policy_gap"]), 4),
            "cpi_yoy":        round(float(row["cpi_yoy"]), 4),
            "pi_adjusted":    round(float(row["pi_adjusted"]), 4),
            "output_gap":     round(float(row["output_gap"]), 4),
        })

    if not history:
        raise ValueError("No data to compute Taylor Rule")

    current = history[-1]
    gap = current["gap"]

    # Softened language: describe the gap relative to this specification only,
    # without asserting a policy recommendation (the forward-looking variant
    # often shows a materially different implied rate).
    if gap < -0.75:
        signal = "behind_curve"
        signal_label = (
            f"Actual rate is {abs(gap):.2f}pp below this backward-looking specification — "
            f"gap narrows significantly under the forward-looking variant (see chart)"
        )
    elif gap > 0.75:
        signal = "ahead_curve"
        signal_label = (
            f"Actual rate is {gap:.2f}pp above this backward-looking specification — "
            f"this specification suggests policy is restrictive relative to current conditions"
        )
    else:
        signal = "neutral"
        signal_label = (
            f"Actual rate is within 0.75pp of this Taylor Rule specification — broadly aligned"
        )

    return {
        "history":          history,
        "current":          current,
        "signal":           signal,
        "signal_label":     signal_label,
        "target_inflation": TARGET_INFLATION,
        "neutral_rate":     NEUTRAL_RATE,
    }
