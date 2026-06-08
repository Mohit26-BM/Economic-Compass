import os
from datetime import date

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ingestion.schemas.raw import EconomicObservation

FRED_BASE = "https://api.stlouisfed.org/fred"

# Key economic series to track
DEFAULT_SERIES = {
    "GDP": "Gross Domestic Product",
    "CPIAUCSL": "Consumer Price Index",
    "UNRATE": "Unemployment Rate",
    "FEDFUNDS": "Federal Funds Rate",
    "T10Y2Y": "10Y-2Y Treasury Spread",
    "HOUST": "Housing Starts",
    "RSXFS": "Advance Retail Sales",
    "USREC":  "NBER Recession Indicator",
    "PAYEMS": "Total Nonfarm Payrolls",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def fetch_series(
    series_id: str,
    observation_start: date | None = None,
    api_key: str | None = None,
) -> list[EconomicObservation]:
    key = api_key or os.environ["FRED_API_KEY"]
    params = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
        "sort_order": "asc",
    }
    if observation_start:
        params["observation_start"] = observation_start.isoformat()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{FRED_BASE}/series/observations", params=params)
        resp.raise_for_status()

    data = resp.json()
    observations = []
    for obs in data.get("observations", []):
        try:
            observations.append(EconomicObservation(
                series_id=series_id,
                observation_date=obs["date"],
                value=obs["value"],
                realtime_start=obs.get("realtime_start"),
                realtime_end=obs.get("realtime_end"),
            ))
        except Exception as e:
            logger.warning(f"Skipping malformed observation {obs}: {e}")

    logger.info(f"Fetched {len(observations)} observations for {series_id}")
    return observations
