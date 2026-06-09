import json
import os
from pathlib import Path

import duckdb
import pandas as pd

ARTIFACTS = Path(os.environ.get("MODEL_ARTIFACTS_PATH", "./ml/artifacts"))


def _load_series(series_id: str, db_path: str = "./data/warehouse.duckdb") -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute("""
        SELECT observation_date, value
        FROM raw.economic_indicators
        WHERE series_id = ? AND value IS NOT NULL
        ORDER BY observation_date
    """, [series_id]).fetchdf()
    con.close()
    df["ds"] = pd.to_datetime(df["observation_date"])
    return df.rename(columns={"value": "y"})[["ds", "y"]].dropna()


def calibrate_series(
    series_id: str,
    cutoff_date: str = "2023-01-01",
    db_path: str = "./data/warehouse.duckdb",
) -> dict:
    df = _load_series(series_id, db_path)
    cutoff = pd.to_datetime(cutoff_date)
    train = df[df["ds"] < cutoff].copy()
    test = df[df["ds"] >= cutoff].copy()

    if len(train) < 24:
        raise ValueError(f"Only {len(train)} training rows (need ≥24)")
    if len(test) < 3:
        raise ValueError(f"Only {len(test)} test rows")

    # Detect frequency from median gap between observations
    gaps = df["ds"].diff().dropna().dt.days.median()
    if gaps <= 2:
        freq = "D"
    elif gaps <= 35:
        freq = "MS"
    else:
        freq = "QS"

    from prophet import Prophet

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        interval_width=0.95,
    )
    model.fit(train)

    future = model.make_future_dataframe(periods=len(test) + 12, freq=freq)
    forecast = model.predict(future)

    forecast_test = forecast[forecast["ds"].isin(test["ds"])][
        ["ds", "yhat", "yhat_lower", "yhat_upper"]
    ]
    merged = test.merge(forecast_test, on="ds")

    if len(merged) == 0:
        raise ValueError("No overlap between forecast dates and test actuals")

    merged["in_interval"] = (
        (merged["y"] >= merged["yhat_lower"]) & (merged["y"] <= merged["yhat_upper"])
    )
    coverage = float(merged["in_interval"].mean())
    mae = float((merged["y"] - merged["yhat"]).abs().mean())
    denom = merged["y"].abs().replace(0.0, float("nan"))
    mape = float(((merged["y"] - merged["yhat"]).abs() / denom).mean() * 100)

    calibration_data = []
    for _, row in merged.iterrows():
        calibration_data.append({
            "ds": row["ds"].strftime("%Y-%m-%d"),
            "actual": round(float(row["y"]), 4),
            "forecast": round(float(row["yhat"]), 4),
            "lower": round(float(row["yhat_lower"]), 4),
            "upper": round(float(row["yhat_upper"]), 4),
            "in_interval": bool(row["in_interval"]),
        })

    result = {
        "series_id": series_id,
        "cutoff_date": cutoff_date,
        "expected_coverage": 0.95,
        "actual_coverage": round(coverage, 4),
        "mae": round(mae, 4),
        "mape": round(mape, 4),
        "n_test": len(merged),
        "calibration_data": calibration_data,
    }

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
