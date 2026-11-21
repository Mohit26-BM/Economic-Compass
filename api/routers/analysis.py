import os
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from api.guards import (
    FORECAST_SERIES,
    cached_on_files,
    public_error,
    rate_limit,
    read_limiter,
    simulate_limiter,
)

DB_PATH = os.environ.get("DUCKDB_PATH", "./data/warehouse.duckdb")
_ARTIFACTS = Path(os.environ.get("MODEL_ARTIFACTS_PATH", "./ml/artifacts"))
_RECESSION_MODEL = str(_ARTIFACTS / "recession_model.joblib")

router = APIRouter(dependencies=[Depends(rate_limit(read_limiter))])


class SimulateRequest(BaseModel):
    """Bounds match the dashboard sliders. Anything outside is rejected, NaN and infinity included."""

    model_config = ConfigDict(extra="forbid")

    fedfunds:  float = Field(ge=0.0, le=10.0, allow_inf_nan=False)
    cpi_yoy:   float = Field(ge=-2.0, le=12.0, allow_inf_nan=False)
    gdp_yoy:   float = Field(ge=-8.0, le=10.0, allow_inf_nan=False)
    unrate:    float = Field(ge=2.0, le=12.0, allow_inf_nan=False)
    t10y2y:    float = Field(ge=-3.0, le=3.5, allow_inf_nan=False)
    houst_yoy: float | None = Field(default=None, ge=-50.0, le=60.0, allow_inf_nan=False)
    rsxfs_yoy: float | None = Field(default=None, ge=-15.0, le=20.0, allow_inf_nan=False)


# Each analysis reads the whole warehouse; results are reused until the data or model changes.
@cached_on_files(DB_PATH, _RECESSION_MODEL)
def _recession(db_path: str):
    from ml.recession.model import predict_recession
    return predict_recession(db_path)


@cached_on_files(DB_PATH)
def _correlation(db_path: str):
    from ml.correlation.analyzer import run_full_analysis
    return run_full_analysis(db_path)


@cached_on_files(DB_PATH)
def _regime(db_path: str):
    from ml.regime.detector import detect_regimes
    return detect_regimes(db_path)


@cached_on_files(DB_PATH)
def _taylor(db_path: str):
    from ml.taylor.rule import compute_taylor_rule
    return compute_taylor_rule(db_path)


@cached_on_files(DB_PATH)
def _sahm(db_path: str):
    from ml.sahm.indicator import compute_sahm
    return compute_sahm(db_path)


@cached_on_files(DB_PATH)
def _conditions(db_path: str):
    from ml.conditions.index import compute_conditions_index
    return compute_conditions_index(db_path)


@cached_on_files(DB_PATH)
def _defaults(db_path: str):
    from ml.simulator.engine import get_defaults
    return get_defaults(db_path)


@router.get("/recession")
def get_recession_probability():
    """Current recession risk score + fitted history from the logistic regression model."""
    try:
        return _recession(DB_PATH)
    except Exception as e:
        raise public_error(e, "Recession model")


@router.get("/correlation")
def get_correlation_analysis():
    """Cross-series lag correlations and Granger causality tests."""
    try:
        return _correlation(DB_PATH)
    except Exception as e:
        raise public_error(e, "Correlation analysis")


@router.get("/regime")
def get_economic_regime():
    """K-means regime detection with timeline and radar chart data."""
    try:
        return _regime(DB_PATH)
    except Exception as e:
        raise public_error(e, "Regime detection")


@router.get("/taylor")
def get_taylor_rule():
    """Taylor Rule implied rate vs actual FEDFUNDS with policy gap."""
    try:
        return _taylor(DB_PATH)
    except Exception as e:
        raise public_error(e, "Taylor Rule")


@router.get("/sahm")
def get_sahm_indicator():
    """Sahm Rule recession indicator + nonfarm payrolls momentum."""
    try:
        return _sahm(DB_PATH)
    except Exception as e:
        raise public_error(e, "Sahm Rule")


@router.get("/simulate-defaults")
def get_simulate_defaults():
    """Current real values for simulator slider initial positions."""
    try:
        return _defaults(DB_PATH)
    except Exception as e:
        raise public_error(e, "Simulator defaults")


@router.post("/simulate", dependencies=[Depends(rate_limit(simulate_limiter))])
def run_simulation(body: SimulateRequest):
    """Run all models against a hypothetical indicator scenario."""
    try:
        from ml.simulator.engine import simulate
        return simulate(body.model_dump(), DB_PATH)
    except Exception as e:
        raise public_error(e, "Simulation")


@router.get("/conditions")
def get_conditions_index():
    """Economic Conditions Index: five category sub-indices + composite score."""
    try:
        return _conditions(DB_PATH)
    except Exception as e:
        raise public_error(e, "Conditions index")


@router.get("/calibration/{series_id}")
def get_calibration(series_id: str):
    """Pre-computed forecast calibration: expected vs actual 95% CI coverage."""
    from fastapi import HTTPException

    if series_id not in FORECAST_SERIES:
        raise HTTPException(status_code=404, detail="Unknown series.")
    try:
        from ml.calibration.backtester import load_calibration
        return load_calibration(series_id)
    except Exception as e:
        raise public_error(e, "Calibration")
