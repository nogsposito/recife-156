import logging

import pandas as pd

from src.config import SILVER_DIR
from src.ingestion.weather import parse_daily_weather
from src.layers.bronze import read_bronze, tickets_path, weather_path
from src.transform.cleaning import clean_tickets, combine_snapshots

log = logging.getLogger(__name__)

TICKETS_PATH = SILVER_DIR / "tickets.parquet"
WEATHER_PATH = SILVER_DIR / "daily_weather.parquet"


def _write(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    log.info("Silver: %d rows written to %s", len(df), path.name)


# One row per ticket: cleaned, standardized and with only its latest snapshot
def build_silver_tickets(years: list[int]) -> pd.DataFrame:
    frames = [clean_tickets(read_bronze(tickets_path(year)), year) for year in years]
    tickets = combine_snapshots(frames, years)
    _write(tickets, TICKETS_PATH)
    return tickets


# One row per day, with the table's column names and types
def build_silver_weather(years: list[int]) -> pd.DataFrame:
    daily = pd.concat([read_bronze(weather_path(year)) for year in years], ignore_index=True)
    weather = (
        parse_daily_weather(daily)
        .drop_duplicates("weather_date", keep="last")
        .sort_values("weather_date", ignore_index=True)
    )
    _write(weather, WEATHER_PATH)
    return weather
