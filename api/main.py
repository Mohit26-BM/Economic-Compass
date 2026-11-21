import os
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api.routers import analysis, lineage, metrics, pipeline

@asynccontextmanager
async def lifespan(_: FastAPI):
    # The first request after a start would otherwise pay for importing the ML libraries and fitting
    # the regime model (tens of seconds on a cold machine). Do that in the background instead.
    if os.environ.get("WARMUP", "1") != "0":
        threading.Thread(target=_warm_up, daemon=True).start()
    yield


def _warm_up() -> None:
    try:
        from api.routers import analysis as a
        for fn in (a._regime, a._recession, a._conditions, a._taylor, a._sahm):
            fn(a.DB_PATH)
        from ml.simulator.engine import _regime_map, _load_monthly_cached
        _load_monthly_cached(a.DB_PATH)
        _regime_map(a.DB_PATH)
    except Exception:
        from loguru import logger
        logger.exception("Warm-up failed (requests will compute on demand)")


app = FastAPI(
    lifespan=lifespan,
    title="Economic Compass API",
    description="Macroeconomic data, model outputs, forecasts, drift checks and lineage (read-only)",
    version="0.2.0",
)

# The API is public and read-only, and uses no cookies or logins, so any website may read it by
# default. Set ALLOWED_ORIGINS (comma separated) to restrict it to your own dashboard.
_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Only where and why, never the submitted value: NaN/Infinity cannot be serialised back to JSON,
    # and echoing arbitrary input into a response is best avoided anyway.
    problems = [{"field": ".".join(str(p) for p in e["loc"]), "problem": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": problems})


app.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics & Drift"])
app.include_router(lineage.router, prefix="/lineage", tags=["Lineage"])
app.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])


@app.get("/health")
def health():
    """Liveness plus a yes/no on the two things the app cannot work without. No paths or schema."""
    db_path = os.environ.get("DUCKDB_PATH", "./data/warehouse.duckdb")
    return {
        "status": "ok",
        "database": os.path.exists(db_path),
        "recession_model": os.path.exists("./ml/artifacts/recession_model.joblib"),
    }
