import os

import duckdb
from fastapi import APIRouter, HTTPException

from api.schemas.responses import PipelineRunResponse, SeriesListResponse

router = APIRouter()


def _get_db():
    path = os.environ.get("DUCKDB_PATH", "./data/warehouse.duckdb")
    return duckdb.connect(path, read_only=True)


@router.get("/series", response_model=SeriesListResponse)
def list_series():
    try:
        con = _get_db()
        rows = con.execute("""
            SELECT series_id, COUNT(*) as row_count,
                   MIN(observation_date)::varchar as first_date,
                   MAX(observation_date)::varchar as last_date
            FROM raw.economic_indicators
            GROUP BY series_id
            ORDER BY series_id
        """).fetchdf()
        con.close()
        return {"series": rows.to_dict("records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/series/{series_id}")
def get_series_data(series_id: str, limit: int = 120):
    try:
        con = _get_db()
        rows = con.execute("""
            SELECT observation_date::varchar as observation_date, value
            FROM (
                SELECT observation_date, value
                FROM raw.economic_indicators
                WHERE series_id = ? AND value IS NOT NULL
                ORDER BY observation_date DESC
                LIMIT ?
            ) sub
            ORDER BY observation_date ASC
        """, [series_id, limit]).fetchdf()
        con.close()
        return {"series_id": series_id, "data": rows.to_dict("records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
