import duckdb
import pandas as pd
from loguru import logger
from prefect import task

from ingestion.schemas.raw import EconomicObservation, IngestionResult
from ingestion.sources.fred import fetch_series


@task(name="fetch-fred-series", retries=2, retry_delay_seconds=30)
async def task_fetch_series(series_id: str) -> list[EconomicObservation]:
    return await fetch_series(series_id)


@task(name="load-to-duckdb")
def task_load_observations(
    observations: list[EconomicObservation],
    db_path: str,
) -> IngestionResult:
    if not observations:
        return IngestionResult(
            series_id="unknown", rows_fetched=0, rows_inserted=0, status="skipped"
        )

    series_id = observations[0].series_id
    df = pd.DataFrame([o.model_dump() for o in observations])

    con = duckdb.connect(db_path)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.economic_indicators (
            series_id       VARCHAR,
            observation_date DATE,
            value           DOUBLE,
            realtime_start  DATE,
            realtime_end    DATE,
            loaded_at       TIMESTAMP DEFAULT current_timestamp
        )
    """)
    # Upsert: delete existing rows for series then re-insert
    con.execute("DELETE FROM raw.economic_indicators WHERE series_id = ?", [series_id])
    con.execute("INSERT INTO raw.economic_indicators SELECT *, current_timestamp FROM df")
    rows = con.execute(
        "SELECT COUNT(*) FROM raw.economic_indicators WHERE series_id = ?", [series_id]
    ).fetchone()[0]
    con.close()

    logger.info(f"Loaded {rows} rows for {series_id}")
    return IngestionResult(
        series_id=series_id,
        rows_fetched=len(observations),
        rows_inserted=rows,
        status="success",
    )
