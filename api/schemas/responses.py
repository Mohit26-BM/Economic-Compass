from pydantic import BaseModel


class SeriesMeta(BaseModel):
    series_id: str
    row_count: int
    first_date: str
    last_date: str


class SeriesListResponse(BaseModel):
    series: list[SeriesMeta]


class PipelineRunResponse(BaseModel):
    status: str
    message: str
