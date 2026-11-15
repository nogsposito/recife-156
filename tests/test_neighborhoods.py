import pandas as pd

from src.dashboard.neighborhoods import describe, neighborhood_stats


def tickets_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "neighborhood_name": ["PINA", "PINA", "PINA", "TORRE", "TORRE", "TORRE"],
            "service_name": ["PODA", "PODA", "PODA", "PODA", "PODA", "PODA"],
            "group": ["Arborização"] * 6,
            "is_open": [True, True, False, True, False, False],
            "opened_on": pd.to_datetime(["2025-01-01", "2025-12-01", "2025-01-01"] * 2),
            "days_to_last_update": [0, 0, 40, 0, 10, 10],
        }
    )


def test_neighborhood_stats_compares_waits_within_the_same_service():
    stats = neighborhood_stats(tickets_frame(), pd.Timestamp("2025-12-31"), "group")

    assert stats.loc["PINA", "open_tickets"] == 2
    assert stats.loc["PINA", "over_180"] == 0.5
    # The city median for PODA is 10 days: Pina took 40 (4x), Torre took 10 (1x)
    assert stats.loc["PINA", "relative_wait"] == 4.0
    assert stats.loc["TORRE", "relative_wait"] == 1.0
    assert stats.loc["TORRE", "top"] == "Arborização"


def test_describe_reads_the_numbers_against_the_city():
    row = pd.Series(
        {
            "open_tickets": 100,
            "over_180": 0.8,
            "relative_wait": 2.0,
            "top": "Drenagem",
            "top_share": 0.4,
        }
    )

    text = describe(row, city_over_180=0.5)

    assert text.startswith("Drenagem puxa a fila: 40% dos 100 pedidos em aberto.")
    assert "acima da cidade (50%)" in text
    assert "2,0 vezes o tempo da cidade" in text
    assert "chuva forte" in text
