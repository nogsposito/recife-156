from datetime import date

import pandas as pd

from src.transform.modeling import build_tables


def test_build_tables_returns_a_star_schema_with_consistent_keys():
    tickets = pd.DataFrame(
        {
            "service_code": [10, 10, 20],
            "service_name": ["LAMPADA APAGADA", "LAMPADA APAGADA (NOVO)", "PODA"],
            "group_code": [4, 4, 3],
            "group_name": ["ILUMINACAO", "ILUMINACAO", "ARBORIZACAO"],
            "neighborhood": ["PINA", "PINA", None],
            "rpa": pd.array([6, 6, None], dtype="Int64"),
            "opened_on": pd.to_datetime(["2024-06-01", "2025-01-04", "2025-01-05"]),
            "status_updated_on": pd.to_datetime(["2024-06-02", "2025-01-04", "2025-01-06"]),
            "status": ["ATENDIDA", "CADASTRADA", "ATENDIDA"],
            "street": ["RUA A", "RUA B", "RUA C"],
            "street_number": ["1", None, "3"],
            "latitude": [None, None, None],
            "longitude": [None, None, None],
            "source_year": [2024, 2025, 2025],
        }
    )
    weather = pd.DataFrame(
        {
            "weather_date": [date(2025, 1, 4), date(2025, 1, 6)],
            "precipitation_mm": [12.0, 0.0],
            "temp_max_c": [30.0, 31.0],
            "temp_min_c": [23.0, 24.0],
            "temp_mean_c": [26.0, 27.0],
        }
    )

    tables = build_tables(tickets, weather)

    assert list(tables) == ["dim_service", "dim_neighborhood", "dim_date", "fact_tickets"]
    service = tables["dim_service"].set_index("service_code")
    # The most recent yearly file decides the service name
    assert service.loc[10, "service_name"] == "LAMPADA APAGADA (NOVO)"
    dim_date = tables["dim_date"].set_index("date_key")
    assert dim_date.loc[date(2025, 1, 4), "day_of_week"] == 6  # Saturday in ISO numbering
    assert dim_date.loc[date(2025, 1, 4), "is_weekend"]
    assert not dim_date.loc[date(2025, 1, 6), "is_weekend"]
    fact = tables["fact_tickets"]
    assert fact["neighborhood_id"].tolist()[:2] == [1, 1]
    assert pd.isna(fact["neighborhood_id"].iloc[2])
    assert fact["opened_on"].iloc[0] == date(2024, 6, 1)
