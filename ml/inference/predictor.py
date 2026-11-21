import os
import warnings

import duckdb
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

DB_PATH = os.environ.get("DUCKDB_PATH", "./data/warehouse.duckdb")

# The model only ever sees the most recent 10 years: older history comes from a different
# economy and makes the fit slow without making the next year's forecast better.
TRAIN_MONTHS = 120
Z_95 = 1.96


def _load_series(series_id: str, db_path: str | None = None) -> pd.Series:
    con = duckdb.connect(db_path or DB_PATH, read_only=True)
    try:
        df = con.execute(
            "SELECT observation_date, value FROM raw.economic_indicators "
            "WHERE series_id = ? ORDER BY observation_date",
            [series_id],
        ).fetchdf()
    finally:
        con.close()

    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df = df.dropna(subset=["value"]).sort_values("observation_date")
    # Everything is put on a monthly grid: quarterly GDP is carried forward up to 3 months,
    # daily series are averaged within the month.
    return (
        df.set_index("observation_date")["value"]
        .resample("MS")
        .mean()
        .ffill(limit=3)
        .dropna()
    )


def forecast_series(s: pd.Series, horizon_months: int = 12) -> list[dict]:
    """
    Holt-Winters exponential smoothing (additive trend, additive 12-month seasonality) on the last
    10 years, falling back to trend-only when the seasonal fit fails.

    The interval is 1.96 x the in-sample one-step error, widened by sqrt(horizon). That assumes
    errors behave like a random walk. The calibration backtest measures how often it holds.
    """
    s = s.iloc[-TRAIN_MONTHS:]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            model = ExponentialSmoothing(
                s, trend="add", seasonal="add", seasonal_periods=12,
                initialization_method="estimated",
            ).fit(optimized=True)
        except Exception:
            model = ExponentialSmoothing(
                s, trend="add", seasonal=None, initialization_method="estimated",
            ).fit(optimized=True)

        fc = model.forecast(horizon_months)
    resid_std = float(model.resid.std())

    results = []
    for i, (date, yhat) in enumerate(fc.items()):
        margin = resid_std * Z_95 * np.sqrt(i + 1)
        results.append(
            {
                "ds": date.strftime("%Y-%m-%d"),
                "yhat": round(float(yhat), 4),
                "yhat_lower": round(float(yhat) - margin, 4),
                "yhat_upper": round(float(yhat) + margin, 4),
            }
        )
    return results


def predict(series_id: str, horizon_months: int = 12) -> list[dict]:
    s = _load_series(series_id)
    if s.empty:
        raise FileNotFoundError(f"No data found for {series_id}")
    if len(s) < 36:
        raise ValueError(f"Not enough history to forecast {series_id}")
    return forecast_series(s, horizon_months)
