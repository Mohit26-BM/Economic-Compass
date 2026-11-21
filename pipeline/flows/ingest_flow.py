import asyncio
import os

from dotenv import load_dotenv
from prefect import flow

load_dotenv()
from prefect.logging import get_run_logger

from ingestion.sources.fred import DEFAULT_SERIES
from pipeline.tasks.common import task_fetch_series, task_load_observations


@flow(name="economic-data-ingestion", log_prints=True)
async def ingest_economic_data(
    series_ids: list[str] | None = None,
    db_path: str | None = None,
):
    logger = get_run_logger()
    db = db_path or os.environ.get("DUCKDB_PATH", "./data/warehouse.duckdb")
    targets = series_ids or list(DEFAULT_SERIES.keys())

    logger.info(f"Starting ingestion for {len(targets)} series → {db}")

    results = []
    for series_id in targets:
        try:
            observations = await task_fetch_series(series_id)
            result = task_load_observations(observations, db, series_id)
        except Exception as e:
            logger.error(f"Failed to ingest {series_id}: {e}")
            from ingestion.schemas.raw import IngestionResult
            result = IngestionResult(
                series_id=series_id, rows_fetched=0, rows_inserted=0,
                status="failed", error=str(e)
            )
        results.append(result)

    succeeded = sum(1 for r in results if r.status == "success")
    logger.info(f"Ingestion complete: {succeeded}/{len(results)} series loaded")
    return results


if __name__ == "__main__":
    import sys

    outcome = asyncio.run(ingest_economic_data())
    failed = [r.series_id for r in outcome if r.status != "success"]
    if failed:
        # A scheduler must be able to see that a run was incomplete.
        print(f"FAILED or skipped: {', '.join(failed)}")
        sys.exit(1)
