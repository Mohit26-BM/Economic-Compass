import os

import duckdb
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from api.guards import FORECAST_SERIES, KNOWN_SERIES, public_error, rate_limit, read_limiter
from monitoring.drift.detector import detect_drift

router = APIRouter(dependencies=[Depends(rate_limit(read_limiter))])

ALL_SERIES = ["GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS", "T10Y2Y", "HOUST", "RSXFS", "PAYEMS"]

# Trending series: must be converted to YoY % change before PSI.
# PSI on levels measures "the economy grew", not behavioral drift.
YOY_SERIES  = {"GDP", "CPIAUCSL", "RSXFS", "PAYEMS", "HOUST"}
LEVEL_SERIES = {"UNRATE", "FEDFUNDS", "T10Y2Y"}

TRANSFORM_LABEL = {
    "GDP":      "GDP growth (YoY %)",
    "CPIAUCSL": "CPI inflation (YoY %)",
    "RSXFS":    "Retail Sales growth (YoY %)",
    "PAYEMS":   "Payrolls growth (YoY %)",
    "HOUST":    "Housing Starts growth (YoY %)",
    "UNRATE":   "Unemployment Rate (level)",
    "FEDFUNDS": "Fed Funds Rate (level)",
    "T10Y2Y":   "10Y-2Y Spread (level)",
}

DB_PATH = os.environ.get("DUCKDB_PATH", "./data/warehouse.duckdb")


def _fetch_monthly(series_id: str) -> pd.DataFrame:
    """Fetch series and resample to monthly frequency.

    GDP is stored as quarterly observations.  Without resampling first,
    pct_change(12) looks back 12 rows = 3 years instead of 12 months,
    producing ref_mean ≈ 16% instead of the correct ≈ 2-3%.
    """
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute("""
        SELECT observation_date, value
        FROM raw.economic_indicators
        WHERE series_id = ?
        ORDER BY observation_date
    """, [series_id]).fetchdf()
    con.close()

    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df = df.dropna(subset=["value"]).sort_values("observation_date")

    # Resample to month-start frequency; forward-fill up to 3 periods to
    # handle quarterly GDP without introducing long gaps.
    df = (
        df.set_index("observation_date")["value"]
        .resample("MS")
        .mean()
        .ffill(limit=3)
        .reset_index()
        .rename(columns={"observation_date": "observation_date"})
    )
    return df.dropna(subset=["value"]).reset_index(drop=True)


def _make_stationary(df: pd.DataFrame, series_id: str) -> pd.DataFrame:
    df = df.copy()
    if series_id in YOY_SERIES:
        df["value"] = df["value"].pct_change(12, fill_method=None) * 100
    return df.dropna(subset=["value"])


def _split_windows(df: pd.DataFrame, reference_months: int, current_months: int):
    cutoff    = df["observation_date"].max() - pd.DateOffset(months=current_months)
    ref_start = cutoff - pd.DateOffset(months=reference_months)
    reference = df[(df["observation_date"] >= ref_start) & (df["observation_date"] < cutoff)].copy()
    current   = df[df["observation_date"] >= cutoff].copy()
    return reference, current


@router.get("/drift")
def get_all_drift(
    reference_months: int = Query(60, ge=24, le=240),
    current_months: int = Query(12, ge=3, le=60),
):
    """PSI drift summary for all tracked series (stationary transforms, monthly resampled)."""
    results = []
    for sid in ALL_SERIES:
        try:
            monthly    = _fetch_monthly(sid)
            if monthly.empty:
                continue
            stationary = _make_stationary(monthly, sid)
            reference, current = _split_windows(stationary, reference_months, current_months)
            if reference.empty or current.empty:
                continue
            result = detect_drift(reference, current, series_id=sid)
            result["transform"]       = "yoy_pct" if sid in YOY_SERIES else "level"
            result["transform_label"] = TRANSFORM_LABEL.get(sid, sid)
            results.append(result)
        except Exception:
            logger.exception(f"Drift check failed for {sid}")
            continue
    return {
        "series":           results,
        "reference_months": reference_months,
        "current_months":   current_months,
    }


@router.get("/drift/{series_id}")
def get_drift_report(
    series_id: str,
    reference_months: int = Query(60, ge=24, le=240),
    current_months: int = Query(12, ge=3, le=60),
):
    """PSI drift report for a single series."""
    if series_id not in KNOWN_SERIES:
        raise HTTPException(status_code=404, detail="Unknown series.")
    try:
        monthly    = _fetch_monthly(series_id)
        if monthly.empty:
            raise HTTPException(status_code=404, detail=f"Series {series_id} not found")
        stationary = _make_stationary(monthly, series_id)
        reference, current = _split_windows(stationary, reference_months, current_months)
        result = detect_drift(reference, current, series_id=series_id)
        result["transform"]       = "yoy_pct" if series_id in YOY_SERIES else "level"
        result["transform_label"] = TRANSFORM_LABEL.get(series_id, series_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise public_error(e, "Drift report")


@router.get("/forecast/{series_id}")
def get_forecast(series_id: str, horizon: int = Query(12, ge=1, le=36)):
    """Trend-and-seasonality extrapolation (Holt-Winters), not an economic forecast. See /analysis/calibration."""
    if series_id not in FORECAST_SERIES:
        raise HTTPException(status_code=404, detail="Unknown series.")
    try:
        from ml.inference.predictor import predict
        return {
            "series_id": series_id,
            "method": "Holt-Winters exponential smoothing on the last 10 years, additive trend and seasonality",
            "forecast": predict(series_id, horizon),
        }
    except Exception as e:
        raise public_error(e, "Forecast")
