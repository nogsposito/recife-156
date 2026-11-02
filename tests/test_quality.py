import pandas as pd
import pytest

from src.quality.checks import DataQualityError, check_tickets, check_weather, enforce


def silver_tickets(**overrides) -> pd.DataFrame:
    tickets = pd.DataFrame(
        {
            "service_code": [10, 10, 20],
            "group_code": [4, 4, 2],
            "opened_on": pd.to_datetime(["2024-01-02", "2024-05-10", "2025-03-01"]),
            "status_updated_on": pd.to_datetime(["2024-01-03", "2024-05-10", "2025-03-09"]),
            "status": ["ATENDIDA", "CADASTRADA", "ATENDIDA"],
            "rpa": pd.array([1, 6, None], dtype="Int64"),
            "latitude": [-8.05, None, -8.10],
            "longitude": [-34.90, None, -34.92],
            "neighborhood": ["BOA VIAGEM", "IBURA", "PINA"],
        }
    )
    return tickets.assign(**overrides)


def failed(results) -> set[str]:
    return {result.name for result in results if not result.passed}


def test_clean_tickets_pass_every_check():
    assert failed(check_tickets(silver_tickets(), years=[2024, 2025])) == set()


def test_broken_tickets_fail_the_matching_checks():
    tickets = silver_tickets(
        opened_on=pd.to_datetime(["2023-12-31", "2024-05-10", "2025-03-01"]),
        status_updated_on=pd.to_datetime(["2024-01-03", "2024-05-01", "2025-03-09"]),
        rpa=pd.array([1, 9, None], dtype="Int64"),
        latitude=[-8.05, 85.0, -8.10],
        longitude=[-34.90, -180.0, -34.92],
        group_code=[4, 5, 2],
    )

    assert failed(check_tickets(tickets, years=[2024, 2025])) == {
        "opened_within_years",
        "status_updated_after_opening",
        "rpa_between_1_and_6",
        "coordinates_inside_recife",
        "one_group_per_service",
    }


def test_weather_must_cover_every_day_with_tickets():
    weather = pd.DataFrame(
        {
            "weather_date": pd.to_datetime(["2024-01-02", "2024-05-10"]).date,
            "precipitation_mm": [0.0, 3.2],
        }
    )

    assert failed(check_weather(weather, silver_tickets())) == {"weather_covers_ticket_days"}


def test_enforce_stops_only_on_error_level_failures():
    results = check_tickets(silver_tickets(status=["ATENDIDA", "NOVA", "ATENDIDA"]), [2024, 2025])
    enforce(results)  # unknown status is only a warning

    broken = check_tickets(silver_tickets(rpa=pd.array([1, 9, None], dtype="Int64")), [2024, 2025])
    with pytest.raises(DataQualityError, match="rpa_between_1_and_6"):
        enforce(broken)
