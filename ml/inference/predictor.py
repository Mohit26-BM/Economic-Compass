import os

import duckdb
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

DB_PATH = os.environ.get("DUCKDB_PATH", "./data/warehouse.duckdb")


def _load_series(series_id: str) -> pd.Series:
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute(
        "SELECT observation_date, value FROM raw.economic_indicators "
        "WHERE series_id = ? ORDER BY observation_date",
        [series_id],
    ).fetchdf()
    con.close()

    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df = df.dropna(subset=["value"]).sort_values("observation_date")
    s = (
        df.set_index("observation_date")["value"]
        .resample("MS")
        .mean()
        .ffill(limit=3)
        .dropna()
    )
    return s


def predict(series_id: str, horizon_months: int = 12) -> list[dict]:
    s = _load_series(series_id)
    if s.empty:
        raise FileNotFoundError(f"No data found for {series_id}")

    # Use last 10 years of data to keep fitting fast
    s = s.iloc[-120:]

    try:
        model = ExponentialSmoothing(
            s,
            trend="add",
            seasonal="add",
            seasonal_periods=12,
            initialization_method="estimated",
        ).fit(optimized=True, disp=False)
    except Exception:
        # Fall back to non-seasonal if not enough data
        model = ExponentialSmoothing(
            s,
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        ).fit(optimized=True, disp=False)

    fc = model.forecast(horizon_months)
    resid_std = float(model.resid.std())

    results = []
    for i, (date, yhat) in enumerate(fc.items()):
        # Widen confidence interval with forecast horizon
        margin = resid_std * 1.96 * np.sqrt(i + 1)
        results.append(
            {
                "ds": date.strftime("%Y-%m-%d"),
                "yhat": round(float(yhat), 4),
                "yhat_lower": round(float(yhat) - margin, 4),
                "yhat_upper": round(float(yhat) + margin, 4),
            }
        )
    return results
