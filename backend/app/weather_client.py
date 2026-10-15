from __future__ import annotations
from datetime import date
import asyncio
import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class WeatherProviderError(Exception):
    pass


async def search_locations(name: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.get(GEOCODING_URL, params={"name": name, "count": 6, "language": "en", "format": "json"})
    if response.status_code != 200:
        raise WeatherProviderError("Location search is temporarily unavailable")
    return response.json().get("results", [])


async def fetch_daily_max_temperature(latitude: float, longitude: float, start: date, end: date) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_max",
        "temperature_unit": "celsius",
        "timezone": "UTC",
    }
    data = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(ARCHIVE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            break
        except httpx.HTTPError as error:
            if attempt == 2:
                raise WeatherProviderError("Historical weather provider is temporarily unavailable") from error
            await asyncio.sleep(0.4 * (attempt + 1))
    if not data.get("daily", {}).get("time"):
        raise WeatherProviderError("The weather provider returned no daily temperature data")
    return data
