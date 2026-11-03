import json
import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.config import RAW_DIR
from src.ingestion.http import HTTP, TIMEOUT
from src.layers.bronze import now_utc, weather_path, write_bronze

log = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
# Center of Recife; the API snaps it to the nearest point of its grid
RECIFE_LATITUDE = -8.05
RECIFE_LONGITUDE = -34.90
# The archive takes a few days to publish recent dates
ARCHIVE_DELAY_DAYS = 7

# API variable -> column in the gold date dimension
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
    response = HTTP.get(ARCHIVE_URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


# The API answers with one list per variable; this turns them into one typed row per day
def parse_daily_weather(daily: pd.DataFrame) -> pd.DataFrame:
    weather = daily[list(DAILY_VARIABLES)].rename(columns=DAILY_VARIABLES).astype("float64")
    weather.insert(0, "weather_date", pd.to_datetime(daily["time"]).dt.date)
    return weather


# Whole calendar years, except that the last one stops where the archive has data
def year_ranges(years: list[int], today: date) -> list[tuple[int, date, date]]:
    last_available = today - timedelta(days=ARCHIVE_DELAY_DAYS)
    ranges = []
    for year in years:
        start, end = date(year, 1, 1), min(date(year, 12, 31), last_available)
        if start <= end:
            ranges.append((year, start, end))
    return ranges


# Brings each year's daily weather into bronze; a year is fetched again only when the range
# already saved does not cover what is needed now
def ingest_weather(years: list[int], manifest: dict, force: bool = False) -> list[int]:
    changed = []
    for year, start, end in year_ranges(years, date.today()):
        key = f"weather/{year}"
        saved = manifest.get(key, {})
        covered = (
            saved.get("start", "9999") <= start.isoformat()
            and saved.get("end", "") >= end.isoformat()
        )
        if covered and weather_path(year).exists() and not force:
            log.info("Weather %s: already in bronze", year)
            continue

        payload = fetch_daily_weather(start, end, force=force)
        rows = write_bronze(pd.DataFrame(payload["daily"]), weather_path(year), ARCHIVE_URL)
        manifest[key] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "rows": rows,
            "ingested_at": now_utc(),
        }
        log.info("Weather %s: %d days written to bronze", year, rows)
        changed.append(year)
    return changed
