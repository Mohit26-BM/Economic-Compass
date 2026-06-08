import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class SimulateRequest(BaseModel):
    fedfunds:  float
    cpi_yoy:   float
    gdp_yoy:   float
    unrate:    float
    t10y2y:    float
    houst_yoy: Optional[float] = None
    rsxfs_yoy: Optional[float] = None

DB_PATH = os.environ.get("DUCKDB_PATH", "./data/warehouse.duckdb")


@router.get("/recession")
def get_recession_probability():
    """Current recession probability + full history from logistic regression model."""
    try:
        from ml.recession.model import predict_recession
        return predict_recession(DB_PATH)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/correlation")
def get_correlation_analysis():
    """Cross-series lag correlations and Granger causality tests."""
    try:
        from ml.correlation.analyzer import run_full_analysis
        return run_full_analysis(DB_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime")
def get_economic_regime():
    """K-means regime detection with timeline and radar chart data."""
    try:
        from ml.regime.detector import detect_regimes
        return detect_regimes(DB_PATH)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/taylor")
def get_taylor_rule():
    """Taylor Rule implied rate vs actual FEDFUNDS with policy gap."""
    try:
        from ml.taylor.rule import compute_taylor_rule
        return compute_taylor_rule(DB_PATH)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sahm")
def get_sahm_indicator():
    """Sahm Rule recession indicator + nonfarm payrolls momentum."""
    try:
        from ml.sahm.indicator import compute_sahm
        return compute_sahm(DB_PATH)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/simulate-defaults")
def get_simulate_defaults():
    """Current real values for simulator slider initial positions."""
    try:
        from ml.simulator.engine import get_defaults
        return get_defaults(DB_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate")
def run_simulation(body: SimulateRequest):
    """Run all models against a hypothetical indicator scenario."""
    try:
        from ml.simulator.engine import simulate
        return simulate(body.model_dump(), DB_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conditions")
def get_conditions_index():
    """Economic Conditions Index: five category sub-indices + composite score."""
    try:
        from ml.conditions.index import compute_conditions_index
        return compute_conditions_index(DB_PATH)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calibration/{series_id}")
def get_calibration(series_id: str):
    """Pre-computed forecast calibration: expected vs actual 95% CI coverage."""
    try:
        from ml.calibration.backtester import load_calibration
        return load_calibration(series_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
