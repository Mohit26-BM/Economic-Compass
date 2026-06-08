import pandas as pd


def build_forecast_features(df: pd.DataFrame, series_id: str) -> pd.DataFrame:
    """Prepare a single series for Prophet/LightGBM forecasting."""
    series = (
        df[df["series_id"] == series_id]
        .sort_values("observation_date")
        .dropna(subset=["value"])
        .rename(columns={"observation_date": "ds", "value": "y"})
        [["ds", "y"]]
        .copy()
    )
    series["ds"] = pd.to_datetime(series["ds"])
    return series


def add_lag_features(df: pd.DataFrame, lags: list[int] = [1, 3, 6, 12]) -> pd.DataFrame:
    """Add lag columns for tree-based forecasting models."""
    df = df.copy().sort_values("ds")
    for lag in lags:
        df[f"lag_{lag}"] = df["y"].shift(lag)
    df["rolling_mean_3"] = df["y"].rolling(3).mean()
    df["rolling_std_3"] = df["y"].rolling(3).std()
    return df.dropna()
