import pandas as pd

from src.ml.features import (
    build_features,
    build_target,
    outcome_is_known,
    recent_counts,
    temporal_split,
)


def tickets_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "opened_on": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-02", "2025-01-05"]),
            "status": ["ATENDIDA", "ATENDIDA", "CADASTRADA", "ATENDIDA"],
            "days_to_last_update": [3, 45, 0, 30],
            "service_name": ["PODA", "PODA", "PODA", "LAMPADA"],
            "group_name": ["ARBORIZACAO", "ARBORIZACAO", "ARBORIZACAO", "ILUMINACAO"],
            "neighborhood_name": ["PINA", "PINA", None, "PINA"],
            "rpa": [6, 6, None, 6],
        }
    )


def rain_frame() -> pd.DataFrame:
    days = pd.date_range("2025-01-01", "2025-01-06")
    return pd.DataFrame({"date_key": days, "precipitation_mm": [10.0, 0.0, 5.0, 0.0, 1.0, 0.0]})


def test_target_counts_only_tickets_resolved_within_30_days():
    # Resolved in 3 days, resolved in 45, still open, resolved exactly on day 30
    assert build_target(tickets_frame()).tolist() == [1, 0, 0, 1]


def test_outcome_is_known_only_for_tickets_older_than_the_horizon():
    tickets = tickets_frame()
    known = outcome_is_known(tickets, reference=pd.Timestamp("2025-02-02"))
    assert known.tolist() == [True, True, True, False]


def test_recent_counts_use_only_days_before_the_opening_day():
    tickets = tickets_frame()
    calendar = pd.date_range("2025-01-01", "2025-01-06")

    counts = recent_counts(tickets, "service_name", 7, calendar)

    # Day 1 sees nothing before it; day 2 sees the one ticket of day 1, not its own day
    assert counts.tolist() == [0, 1, 1, 0]


def test_build_features_has_calendar_rain_and_demand_columns():
    features = build_features(tickets_frame(), rain_frame())

    assert features.loc[0, "day_of_week"] == 3  # 2025-01-01 was a Wednesday
    assert features.loc[3, "is_weekend"] == 1  # 2025-01-05 was a Sunday
    # Rain of the opening day plus the two days before: 5 + 0 + 1 on 2025-01-05
    assert features.loc[3, "rain_3d_mm"] == 6.0
    assert features.loc[3, "neighborhood_demand_30d"] == 2


def test_temporal_split_leaves_a_horizon_long_gap_before_the_test_months():
    split = temporal_split(pd.Timestamp("2025-12-31"), test_months=5)

    assert split.test_end == pd.Timestamp("2025-12-01")
    assert split.test_start == pd.Timestamp("2025-07-01")
    assert split.train_end == pd.Timestamp("2025-05-31")
