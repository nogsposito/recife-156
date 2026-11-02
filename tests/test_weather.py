from datetime import date

from src.ingestion.weather import parse_daily_weather


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

    weather = parse_daily_weather(payload)

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
