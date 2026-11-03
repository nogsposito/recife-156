from dataclasses import dataclass

import pandas as pd
from sqlalchemy import Engine, text

# The question the model answers: will this ticket be resolved within 30 days of opening?
HORIZON_DAYS = 30
TARGET = "resolved_within_30d"

CATEGORICAL = ["service_name", "group_name", "neighborhood_name", "rpa"]
NUMERIC = [
    "month",
    "day_of_week",
    "is_weekend",
    "rain_3d_mm",
    "service_demand_7d",
    "neighborhood_demand_30d",
]
FEATURES = CATEGORICAL + NUMERIC


def load_model_data(engine: Engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    with engine.connect() as connection:
        tickets = pd.read_sql(text("SELECT * FROM v_tickets"), connection)
        rain = pd.read_sql(text("SELECT date_key, precipitation_mm FROM dim_date"), connection)
    tickets["opened_on"] = pd.to_datetime(tickets["opened_on"])
    tickets["status_updated_on"] = pd.to_datetime(tickets["status_updated_on"])
    rain["date_key"] = pd.to_datetime(rain["date_key"])
    return tickets, rain


def build_target(tickets: pd.DataFrame) -> pd.Series:
    resolved = tickets["status"].eq("ATENDIDA") & tickets["days_to_last_update"].le(HORIZON_DAYS)
    return resolved.astype(int).rename(TARGET)


# The 30-day outcome is only known for tickets opened at least 30 days before the data ends;
# a ticket opened last week and still open may yet be resolved in time
def outcome_is_known(tickets: pd.DataFrame, reference: pd.Timestamp) -> pd.Series:
    return tickets["opened_on"] <= reference - pd.Timedelta(days=HORIZON_DAYS)


# Tickets opened in the previous days (the opening day itself is left out), per service or
# neighborhood: a demand signal that is already known when a new ticket arrives
def recent_counts(
    tickets: pd.DataFrame, key: str, window_days: int, calendar: pd.DatetimeIndex
) -> pd.Series:
    daily = tickets.groupby(["opened_on", key]).size().unstack(fill_value=0)
    previous = daily.reindex(calendar, fill_value=0).rolling(window_days, min_periods=1).sum()
    previous = previous.shift(1).fillna(0)
    lookup = previous.stack()
    keys = pd.MultiIndex.from_arrays([tickets["opened_on"], tickets[key]])
    return pd.Series(lookup.reindex(keys).fillna(0).to_numpy(), index=tickets.index)


# Everything here is known on the day the ticket is opened, so the model can use it then
def build_features(tickets: pd.DataFrame, rain: pd.DataFrame) -> pd.DataFrame:
    calendar = pd.date_range(rain["date_key"].min(), rain["date_key"].max(), freq="D")
    daily_rain = rain.set_index("date_key")["precipitation_mm"].reindex(calendar)
    rain_3d = daily_rain.rolling(3, min_periods=1).sum()
    opened = tickets["opened_on"]
    return pd.DataFrame(
        {
            "service_name": tickets["service_name"],
            "group_name": tickets["group_name"],
            "neighborhood_name": tickets["neighborhood_name"],
            "rpa": tickets["rpa"],
            "month": opened.dt.month,
            "day_of_week": opened.dt.day_of_week + 1,
            "is_weekend": (opened.dt.day_of_week >= 5).astype(int),
            "rain_3d_mm": rain_3d.reindex(opened).to_numpy(),
            "service_demand_7d": recent_counts(tickets, "service_name", 7, calendar),
            "neighborhood_demand_30d": recent_counts(tickets, "neighborhood_name", 30, calendar),
        },
        index=tickets.index,
    )


# Categories are fixed from the training data; a value never seen in training becomes
# missing, which the model handles
def to_model_input(features: pd.DataFrame, categories: dict[str, list]) -> pd.DataFrame:
    model_input = features[FEATURES].copy()
    for column in CATEGORICAL:
        model_input[column] = pd.Categorical(model_input[column], categories=categories[column])
    return model_input


@dataclass(frozen=True)
class TemporalSplit:
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


# Train on the past, test on the most recent months with a known outcome. The gap between
# them is the horizon itself, so no training label depends on what happened in the test window.
def temporal_split(reference: pd.Timestamp, test_months: int = 5) -> TemporalSplit:
    test_end = (reference - pd.Timedelta(days=HORIZON_DAYS)).normalize()
    test_start = (test_end - pd.DateOffset(months=test_months)).normalize().replace(day=1)
    train_end = test_start - pd.Timedelta(days=HORIZON_DAYS + 1)
    return TemporalSplit(train_end, test_start, test_end)
