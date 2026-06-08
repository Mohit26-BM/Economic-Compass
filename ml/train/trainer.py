import os
from pathlib import Path

import joblib
import pandas as pd
from loguru import logger
from prophet import Prophet

from ml.features.engineering import build_forecast_features

ARTIFACTS = Path(os.environ.get("MODEL_ARTIFACTS_PATH", "./ml/artifacts"))


def train_prophet(df: pd.DataFrame, series_id: str, horizon_months: int = 12) -> dict:
    series = build_forecast_features(df, series_id)
    if len(series) < 24:
        raise ValueError(f"Not enough data to train for {series_id} (need ≥24 months)")

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        interval_width=0.95,
    )
    model.fit(series)

    future = model.make_future_dataframe(periods=horizon_months, freq="MS")
    forecast = model.predict(future)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACTS / f"{series_id}_prophet.joblib"
    joblib.dump(model, artifact_path)
    logger.info(f"Model saved to {artifact_path}")

    return {
        "series_id": series_id,
        "artifact_path": str(artifact_path),
        "training_rows": len(series),
        "forecast_horizon": horizon_months,
        "forecast": forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(
            horizon_months
        ).to_dict("records"),
    }
