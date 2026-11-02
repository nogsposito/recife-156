from datetime import date

import pandas as pd

from src.ingestion.weather import parse_daily_weather, year_ranges


def test_parse_daily_weather_returns_one_row_per_day_with_table_columns():
    payload = {
        "daily": {
            "time": ["2024-06-01", "2024-06-02"],
            "precipitation_sum": [42.5, None],
            "temperature_2m_max": [28.1, 29.0],
            "temperature_2m_min": [22.4, 23.0],
            "temperature_2m_mean": [25.0, 25.8],
        }
    }

    weather = parse_daily_weather(pd.DataFrame(payload["daily"]))

    assert list(weather.columns) == [
        "weather_date",
        "precipitation_mm",
        "temp_max_c",
        "temp_min_c",
        "temp_mean_c",
    ]
    assert weather["weather_date"].tolist() == [date(2024, 6, 1), date(2024, 6, 2)]
    assert weather["precipitation_mm"].iloc[0] == 42.5
    assert weather["precipitation_mm"].isna().iloc[1]


def test_year_ranges_cover_whole_years_and_stop_before_the_archive_delay():
    ranges = year_ranges([2024, 2025, 2026], today=date(2025, 3, 10))

    assert ranges == [
        (2024, date(2024, 1, 1), date(2024, 12, 31)),
        (2025, date(2025, 1, 1), date(2025, 3, 3)),
    ]
