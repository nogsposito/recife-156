import argparse
import logging

from src.config import YEARS
from src.db.load import finish_run, get_engine, load_gold, save_quality_checks, start_run
from src.ingestion.ckan import ingest_tickets
from src.ingestion.weather import ingest_weather
from src.layers.bronze import load_manifest, save_manifest
from src.layers.silver import build_silver_tickets, build_silver_weather
from src.quality.checks import check_tickets, check_weather, enforce
from src.transform.modeling import build_tables

log = logging.getLogger("pipeline")


# Sources -> landing -> bronze. Only what changed since the last run is downloaded again.
def run_ingest(years: list[int], full_refresh: bool = False) -> str:
    manifest = load_manifest()
    changed_tickets = ingest_tickets(years, manifest, force=full_refresh)
    changed_weather = ingest_weather(years, manifest, force=full_refresh)
    save_manifest(manifest)
    changed = [f"tickets/{y}" for y in changed_tickets] + [f"weather/{y}" for y in changed_weather]
    log.info("Ingest: %s", ", ".join(changed) if changed else "nothing changed")
    return ",".join(changed) or "none"


# Bronze -> silver -> quality gate -> gold, with the run recorded in ops.pipeline_runs
def run_load(years: list[int], changed_inputs: str) -> None:
    engine = get_engine()
    run_id = start_run(engine, years, changed_inputs)
    try:
        tickets = build_silver_tickets(years)
        weather = build_silver_weather(years)
        results = check_tickets(tickets, years) + check_weather(weather, tickets)
        save_quality_checks(engine, run_id, results)
        enforce(results)
        load_gold(engine, build_tables(tickets, weather))
    except Exception as error:
        finish_run(engine, run_id, "failed", message=str(error)[:500])
        raise
    finish_run(engine, run_id, "success", silver_rows=len(tickets), gold_rows=len(tickets))
    log.info("Run %d finished: %d tickets in gold", run_id, len(tickets))


def main() -> None:
    parser = argparse.ArgumentParser(description="Recife 156 data pipeline")
    parser.add_argument("--step", choices=["all", "ingest", "load"], default="all")
    parser.add_argument(
        "--full-refresh", action="store_true", help="download and rebuild everything"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    log.info("Years: %s | step: %s", YEARS, args.step)

    changed = "not checked"
    if args.step in ("all", "ingest"):
        changed = run_ingest(YEARS, full_refresh=args.full_refresh)
    if args.step in ("all", "load"):
        run_load(YEARS, changed)


if __name__ == "__main__":
    main()
