import os
from pathlib import Path

import joblib
import pandas as pd
from loguru import logger

ARTIFACTS = Path(os.environ.get("MODEL_ARTIFACTS_PATH", "./ml/artifacts"))


def load_model(series_id: str):
    path = ARTIFACTS / f"{series_id}_prophet.joblib"
    if not path.exists():
        raise FileNotFoundError(f"No trained model found for {series_id} at {path}")
    return joblib.load(path)


def predict(series_id: str, horizon_months: int = 12) -> list[dict]:
    model = load_model(series_id)
    future = model.make_future_dataframe(periods=horizon_months, freq="MS")
    forecast = model.predict(future)
    result = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(horizon_months)
    result["ds"] = result["ds"].dt.strftime("%Y-%m-%d")
    logger.info(f"Generated {horizon_months}m forecast for {series_id}")
    return result.to_dict("records")
