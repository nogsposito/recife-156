from src.ingestion.ckan import pick_latest_per_year


def test_pick_latest_per_year_keeps_most_recent_csv_and_skips_other_files():
    resources = [
        {"id": "old", "name": "2025 - Central 156", "format": "CSV", "last_modified": "2026-03-02"},
        {"id": "new", "name": "2025 - Central 156", "format": "CSV", "last_modified": "2026-03-04"},
        {"id": "2024", "name": "2024 - Central 156", "format": "CSV", "last_modified": None,
         "created": "2026-03-01"},
        {"id": "dict", "name": "Dicionário de Dados", "format": "JSON"},
        {"id": "pdf", "name": "2025 - Dicionário", "format": "PDF"},
    ]  # fmt: skip

    latest = pick_latest_per_year(resources)

    assert {year: resource["id"] for year, resource in latest.items()} == {
        2025: "new",
        2024: "2024",
    }
