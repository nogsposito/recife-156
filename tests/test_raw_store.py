import pandas as pd

from src.nosql.raw_store import needs_reload, ticket_documents


def test_ticket_documents_keep_original_columns_and_turn_missing_values_into_null():
    bronze = pd.DataFrame(
        {
            "BAIRRO": ["Pina", None],
            "SITUACAO": ["ATENDIDA", "CADASTRADA"],
            "_source": ["https://example.org/156_2024.csv"] * 2,
            "_ingested_at": ["2026-11-03T00:00:00+00:00"] * 2,
        }
    )

    documents = ticket_documents(bronze, 2024)

    assert documents[0] == {
        "source_year": 2024,
        "source": "https://example.org/156_2024.csv",
        "ingested_at": "2026-11-03T00:00:00+00:00",
        "record": {"BAIRRO": "Pina", "SITUACAO": "ATENDIDA"},
    }
    assert documents[1]["record"]["BAIRRO"] is None


def test_needs_reload_only_when_the_bronze_version_changed():
    entry = {"sha256": "abc", "rows": 10}

    assert needs_reload(entry, None)
    assert not needs_reload(entry, {"version": {"sha256": "abc", "rows": 10}})
    assert needs_reload(entry, {"version": {"sha256": "old", "rows": 10}})
