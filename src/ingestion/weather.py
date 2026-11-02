import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from src.config import RAW_DIR

log = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
# Center of Recife; the API snaps it to the nearest point of its grid
RECIFE_LATITUDE = -8.05
RECIFE_LONGITUDE = -34.90

# API variable -> column in the daily_weather table
DAILY_VARIABLES = {
    "precipitation_sum": "precipitation_mm",
    "temperature_2m_max": "temp_max_c",
    "temperature_2m_min": "temp_min_c",
    "temperature_2m_mean": "temp_mean_c",
}


def raw_weather_path(start: date, end: date) -> Path:
    return RAW_DIR / f"weather_{start}_{end}.json"


# Downloads daily weather for the period and keeps the raw JSON; a cached file is reused
def fetch_daily_weather(start: date, end: date, force: bool = False) -> dict:
    path = raw_weather_path(start, end)
    if path.exists() and not force:
        log.info("Weather: using cached file %s", path.name)
        return json.loads(path.read_text(encoding="utf-8"))

    params = {
        "latitude": RECIFE_LATITUDE,
        "longitude": RECIFE_LONGITUDE,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": "America/Recife",
    }
    log.info("Weather: downloading %s to %s from Open-Meteo", start, end)
    response = requests.get(ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


# The API answers with one list per variable; this turns them into one row per day
def parse_daily_weather(payload: dict) -> pd.DataFrame:
    daily = pd.DataFrame(payload["daily"])
    weather = daily[list(DAILY_VARIABLES)].rename(columns=DAILY_VARIABLES)
    weather.insert(0, "weather_date", pd.to_datetime(daily["time"]).dt.date)
    return weather
