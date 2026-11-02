import argparse
import logging

from src.config import YEARS
from src.db.load import load_tables
from src.ingestion.ckan import ingest
from src.ingestion.weather import fetch_daily_weather, parse_daily_weather
from src.transform.cleaning import clean_tickets, combine_snapshots, read_raw_csv
from src.transform.modeling import build_tables

log = logging.getLogger("pipeline")


# Also downloads any missing raw file, so "load" works on a fresh clone. Weather is fetched
# for exactly the days the tickets cover, so every ticket date has a weather row.
def run_load(years: list[int], force_download: bool = False) -> None:
    paths = ingest(years, force=force_download)
    frames = [
        clean_tickets(read_raw_csv(path), year) for year, path in zip(years, paths, strict=True)
    ]
    tickets = combine_snapshots(frames, years)
    first_day, last_day = tickets["opened_on"].min().date(), tickets["opened_on"].max().date()
    weather = parse_daily_weather(fetch_daily_weather(first_day, last_day, force=force_download))
    load_tables(build_tables(tickets, weather))


def main() -> None:
    parser = argparse.ArgumentParser(description="Recife 156 data pipeline")
    parser.add_argument("--step", choices=["all", "ingest", "load"], default="all")
    parser.add_argument("--force-download", action="store_true", help="ignore cached raw files")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    log.info("Years: %s | step: %s", YEARS, args.step)

    if args.step == "ingest":
        ingest(YEARS, force=args.force_download)
    if args.step in ("all", "load"):
        run_load(YEARS, force_download=args.force_download)


if __name__ == "__main__":
    main()
