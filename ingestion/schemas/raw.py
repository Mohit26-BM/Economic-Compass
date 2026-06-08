from datetime import date
from pydantic import BaseModel, field_validator


class EconomicObservation(BaseModel):
    series_id: str
    observation_date: date
    value: float | None
    realtime_start: date | None = None
    realtime_end: date | None = None

    @field_validator("value", mode="before")
    @classmethod
    def parse_fred_missing(cls, v):
        return None if v == "." else v


class IngestionResult(BaseModel):
    series_id: str
    rows_fetched: int
    rows_inserted: int
    status: str
    error: str | None = None
