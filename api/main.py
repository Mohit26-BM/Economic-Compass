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
    import os, duckdb, traceback
    result = {
        "status": "ok",
        "cwd": os.getcwd(),
        "db_exists": os.path.exists("./data/warehouse.duckdb"),
        "artifacts_exist": os.path.exists("./ml/artifacts/recession_model.joblib"),
    }
    try:
        con = duckdb.connect("./data/warehouse.duckdb", read_only=True)
        schemas = con.execute("SHOW SCHEMAS").fetchall()
        result["schemas"] = [s[0] for s in schemas]
        tables = con.execute("SHOW ALL TABLES").fetchdf()
        result["tables"] = tables[["schema_name","table_name"]].to_dict("records")
        con.close()
    except Exception as e:
        result["db_error"] = traceback.format_exc()
    return result
