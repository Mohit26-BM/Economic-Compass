from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api.routers import analysis, lineage, metrics, pipeline

app = FastAPI(
    title="Data Pipeline Platform API",
    description="Pipeline health, drift metrics, forecasts, and lineage",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics & Drift"])
app.include_router(lineage.router, prefix="/lineage", tags=["Lineage"])
app.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])


@app.get("/health")
def health():
    import os
    return {
        "status": "ok",
        "cwd": os.getcwd(),
        "db_exists": os.path.exists("./data/warehouse.duckdb"),
        "artifacts_exist": os.path.exists("./ml/artifacts/recession_model.joblib"),
    }
