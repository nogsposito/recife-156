import pandas as pd

FACT_COLUMNS = [
    "service_code",
    "neighborhood_id",
    "opened_on",
    "status",
    "status_updated_on",
    "street",
    "street_number",
    "latitude",
    "longitude",
    "source_year",
]


# Calendar attributes plus the day's weather; covers every day with weather data
def build_dim_date(weather: pd.DataFrame) -> pd.DataFrame:
    days = pd.to_datetime(weather["weather_date"])
    return pd.DataFrame(
        {
            "date_key": days.dt.date,
            "year": days.dt.year,
            "month": days.dt.month,
            # ISO numbering: 1 is Monday, 7 is Sunday
            "day_of_week": days.dt.day_of_week + 1,
            "is_weekend": days.dt.day_of_week >= 5,
            "precipitation_mm": weather["precipitation_mm"],
            "temp_max_c": weather["temp_max_c"],
            "temp_min_c": weather["temp_min_c"],
            "temp_mean_c": weather["temp_mean_c"],
        }
    )


# Splits the silver tickets and weather into the star schema of sql/schema.sql
def build_tables(tickets: pd.DataFrame, weather: pd.DataFrame) -> dict[str, pd.DataFrame]:
    # Names can change between yearly files; the most recent file wins
    latest_first = tickets.sort_values("source_year", ascending=False, kind="stable")
    dim_service = latest_first.drop_duplicates("service_code")[
        ["service_code", "service_name", "group_code", "group_name"]
    ].sort_values("service_code")

    # A few rows carry a wrong RPA, so each neighborhood takes its most frequent one
    dim_neighborhood = (
        tickets.dropna(subset=["neighborhood", "rpa"])
        .groupby("neighborhood")["rpa"]
        .agg(lambda rpa: rpa.mode().iloc[0])
        .reset_index()
        .rename(columns={"neighborhood": "neighborhood_name"})
    )
    dim_neighborhood.insert(0, "neighborhood_id", range(1, len(dim_neighborhood) + 1))

    neighborhood_ids = dim_neighborhood.set_index("neighborhood_name")["neighborhood_id"]
    fact = tickets.assign(
        neighborhood_id=tickets["neighborhood"].map(neighborhood_ids).astype("Int64"),
        opened_on=tickets["opened_on"].dt.date,
        status_updated_on=tickets["status_updated_on"].dt.date,
    )
    # Dimensions first, so the fact's foreign keys find their rows during the load
    return {
        "dim_service": dim_service,
        "dim_neighborhood": dim_neighborhood,
        "dim_date": build_dim_date(weather),
        "fact_tickets": fact[FACT_COLUMNS],
    }
