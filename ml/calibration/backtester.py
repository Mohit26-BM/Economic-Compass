"""
Honest check of the forecasts the API actually serves (Holt-Winters, see ml/inference/predictor.py).

A single train/test split says little with monthly data, so the backtest is a rolling origin: every
6 months from 2012, fit on the data available at that date, forecast the next 12 months, and compare
with what really happened. Results are reported overall and by horizon, next to a "nothing changes"
benchmark. A forecast that cannot beat that benchmark is not adding information.
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from ml.inference.predictor import _load_series, forecast_series

ARTIFACTS = Path(os.environ.get("MODEL_ARTIFACTS_PATH", "./ml/artifacts"))

FIRST_ORIGIN = "2012-01-01"
ORIGIN_STEP_MONTHS = 6
HORIZON = 12


def calibrate_series(
    series_id: str,
    cutoff_date: str = "2023-01-01",
    db_path: str = "./data/warehouse.duckdb",
    write: bool = True,
) -> dict:
    """
    cutoff_date is the origin shown in the dashboard chart. The coverage and error statistics come
    from ALL origins.
    """
    s = _load_series(series_id, db_path)
    if len(s) < 120:
        raise ValueError(f"Only {len(s)} monthly observations (need at least 120)")

    last = s.index[-1]
    origins = [
        o for o in pd.date_range(FIRST_ORIGIN, last - pd.DateOffset(months=3), freq=f"{ORIGIN_STEP_MONTHS}MS")
        if o <= last
    ]
    if pd.Timestamp(cutoff_date) not in origins:
        origins.append(pd.Timestamp(cutoff_date))

    rows = []
    for origin in origins:
        train = s[s.index < origin]
        actual = s[s.index >= origin].iloc[:HORIZON]
        if len(train) < 60 or actual.empty:
            continue
        fc = pd.DataFrame(forecast_series(train, HORIZON))
        fc["ds"] = pd.to_datetime(fc["ds"])
        fc = fc.set_index("ds")
        naive = float(train.iloc[-1])
        for h, (ds, y) in enumerate(actual.items(), start=1):
            if ds not in fc.index:
                continue
            f = fc.loc[ds]
            rows.append({
                "origin": origin, "ds": ds, "h": h, "y": float(y), "yhat": float(f["yhat"]),
                "lower": float(f["yhat_lower"]), "upper": float(f["yhat_upper"]), "naive": naive,
            })

    if not rows:
        raise ValueError("No overlap between forecasts and actuals")

    df = pd.DataFrame(rows)
    df["in_interval"] = (df["y"] >= df["lower"]) & (df["y"] <= df["upper"])
    df["abs_err"] = (df["y"] - df["yhat"]).abs()
    df["naive_err"] = (df["y"] - df["naive"]).abs()

    denom = df["y"].abs().replace(0.0, np.nan)
    mape = float((df["abs_err"] / denom).mean() * 100)
    mae = float(df["abs_err"].mean())
    naive_mae = float(df["naive_err"].mean())

    def band(lo: int, hi: int) -> dict:
        d = df[(df["h"] >= lo) & (df["h"] <= hi)]
        return {"coverage": round(float(d["in_interval"].mean()), 4), "n": int(len(d))} if len(d) else None

    shown = df[df["origin"] == pd.Timestamp(cutoff_date)]
    calibration_data = [
        {
            "ds": r["ds"].strftime("%Y-%m-%d"),
            "actual": round(r["y"], 4),
            "forecast": round(r["yhat"], 4),
            "lower": round(r["lower"], 4),
            "upper": round(r["upper"], 4),
            "in_interval": bool(r["in_interval"]),
        }
        for _, r in shown.iterrows()
    ]

    result = {
        "series_id": series_id,
        "method": "Holt-Winters (as served), rolling-origin backtest",
        "cutoff_date": cutoff_date,
        "first_origin": FIRST_ORIGIN,
        "n_origins": int(df["origin"].nunique()),
        "expected_coverage": 0.95,
        "actual_coverage": round(float(df["in_interval"].mean()), 4),
        "coverage_by_horizon": {
            "months_1_3": band(1, 3), "months_4_6": band(4, 6), "months_7_12": band(7, 12),
        },
        "mae": round(mae, 4),
        "mape": round(mape, 4),
        "naive_mae": round(naive_mae, 4),
        # < 1 means the forecast beat "nothing changes"; > 1 means it did worse.
        "mae_vs_naive": round(mae / naive_mae, 4) if naive_mae > 0 else None,
        "n_test": int(len(df)),
        "calibration_data": calibration_data,
    }

    if write:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        with open(ARTIFACTS / f"calibration_{series_id}.json", "w") as f:
            json.dump(result, f)

    return result


def load_calibration(series_id: str) -> dict:
    path = ARTIFACTS / f"calibration_{series_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No calibration for {series_id}. Run: python calibrate_all.py"
        )
    with open(path) as f:
        return json.load(f)
