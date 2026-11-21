import os
import re

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from api.guards import KNOWN_SERIES, public_error, rate_limit, read_limiter
from api.schemas.responses import SeriesListResponse

router = APIRouter(dependencies=[Depends(rate_limit(read_limiter))])

_SERIES_ID = re.compile(r"^[A-Z0-9]{1,20}$")


def _get_db():
    path = os.environ.get("DUCKDB_PATH", "./data/warehouse.duckdb")
    return duckdb.connect(path, read_only=True)


@router.get("/series", response_model=SeriesListResponse)
def list_series():
    try:
        con = _get_db()
        try:
            rows = con.execute("""
                SELECT series_id, COUNT(*) as row_count,
                       MIN(observation_date)::varchar as first_date,
                       MAX(observation_date)::varchar as last_date
                FROM raw.economic_indicators
                GROUP BY series_id
                ORDER BY series_id
            """).fetchdf()
        finally:
            con.close()
        return {"series": rows.to_dict("records")}
    except Exception as e:
        raise public_error(e, "Series list")


@router.get("/series/{series_id}")
def get_series_data(
    series_id: str = Path(..., pattern=_SERIES_ID.pattern),
    limit: int = Query(120, ge=1, le=2000),
):
    if series_id not in KNOWN_SERIES:
        raise HTTPException(status_code=404, detail="Unknown series.")
    try:
        con = _get_db()
        try:
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
        finally:
            con.close()
        return {"series_id": series_id, "data": rows.to_dict("records")}
    except Exception as e:
        raise public_error(e, "Series data")
