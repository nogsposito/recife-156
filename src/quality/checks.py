import logging
from dataclasses import dataclass

import pandas as pd

from src.transform.cleaning import LATITUDE_RANGE, LONGITUDE_RANGE

log = logging.getLogger(__name__)

KNOWN_STATUSES = {
    "ATENDIDA",
    "CADASTRADA",
    "PREPARACAO",
    "EXECUCAO",
    "PENDENCIA",
    "FISCALIZACAO",
    "MONITORAMENTO",
}
MAX_MISSING_NEIGHBORHOOD_SHARE = 0.01


# "error" stops the pipeline before the gold load; "warning" is only recorded
@dataclass
class CheckResult:
    name: str
    severity: str
    passed: bool
    details: str


class DataQualityError(Exception):
    pass


def _check(name: str, severity: str, failures: int, total: int, what: str) -> CheckResult:
    details = f"{failures} of {total} rows {what}" if failures else f"all {total} rows ok"
    return CheckResult(name, severity, failures == 0, details)


def check_tickets(tickets: pd.DataFrame, years: list[int]) -> list[CheckResult]:
    total = len(tickets)
    required = tickets[["service_code", "opened_on", "status"]].isna().any(axis=1)
    inside = tickets["latitude"].between(*LATITUDE_RANGE) & tickets["longitude"].between(
        *LONGITUDE_RANGE
    )
    groups_per_service = tickets.groupby("service_code")["group_code"].nunique()
    missing_neighborhood = tickets["neighborhood"].isna().mean() if total else 0.0
    return [
        CheckResult("tickets_not_empty", "error", total > 0, f"{total} rows"),
        _check("required_fields_present", "error", required.sum(), total, "miss a key field"),
        _check(
            "opened_within_years",
            "error",
            (~tickets["opened_on"].dt.year.isin(years)).sum(),
            total,
            f"opened outside {years}",
        ),
        _check(
            "status_updated_after_opening",
            "error",
            (tickets["status_updated_on"] < tickets["opened_on"]).sum(),
            total,
            "updated before being opened",
        ),
        _check(
            "rpa_between_1_and_6",
            "error",
            (tickets["rpa"].notna() & ~tickets["rpa"].between(1, 6)).sum(),
            total,
            "have an invalid RPA",
        ),
        _check(
            "coordinates_inside_recife",
            "error",
            (tickets["latitude"].notna() & ~inside).sum(),
            total,
            "have coordinates outside Recife",
        ),
        _check(
            "one_group_per_service",
            "error",
            (groups_per_service > 1).sum(),
            len(groups_per_service),
            "services belong to more than one group",
        ),
        _check(
            "known_statuses",
            "warning",
            (~tickets["status"].isin(KNOWN_STATUSES)).sum(),
            total,
            "have a status never seen before",
        ),
        CheckResult(
            "few_missing_neighborhoods",
            "warning",
            missing_neighborhood <= MAX_MISSING_NEIGHBORHOOD_SHARE,
            f"{missing_neighborhood:.2%} of rows without neighborhood",
        ),
    ]


def check_weather(weather: pd.DataFrame, tickets: pd.DataFrame) -> list[CheckResult]:
    days = pd.to_datetime(weather["weather_date"])
    missing_days = set(tickets["opened_on"].dt.normalize()) - set(days)
    return [
        _check(
            "one_weather_row_per_day", "error", days.duplicated().sum(), len(days), "repeat a day"
        ),
        CheckResult(
            "weather_covers_ticket_days",
            "error",
            not missing_days,
            f"{len(missing_days)} ticket days without weather"
            + (f", first {min(missing_days):%Y-%m-%d}" if missing_days else ""),
        ),
        _check(
            "precipitation_not_negative",
            "error",
            (weather["precipitation_mm"] < 0).sum(),
            len(weather),
            "have negative rain",
        ),
    ]


# Logs every result and raises if any error-level check failed
def enforce(results: list[CheckResult]) -> None:
    for result in results:
        level = logging.INFO if result.passed else logging.WARNING
        log.log(level, "Quality %s [%s]: %s", result.name, result.severity, result.details)
    failed = [r.name for r in results if r.severity == "error" and not r.passed]
    if failed:
        raise DataQualityError(f"Quality checks failed: {', '.join(failed)}")
