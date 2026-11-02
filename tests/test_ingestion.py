import hashlib

import pytest

from src.ingestion import ckan
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


RESOURCE = {
    "id": "r2024",
    "name": "2024 - Central 156",
    "format": "CSV",
    "last_modified": "2026-05-01",
    "url": "https://example.org/156_2024.csv",
}


def test_ingest_tickets_skips_a_year_whose_portal_version_is_already_in_bronze(
    tmp_path, monkeypatch
):
    bronze_file = tmp_path / "data.parquet"
    bronze_file.write_bytes(b"existing")
    monkeypatch.setattr(ckan, "fetch_resources", lambda: [RESOURCE])
    monkeypatch.setattr(ckan, "tickets_path", lambda year: bronze_file)
    monkeypatch.setattr(ckan, "download_file", lambda *_: pytest.fail("should not download"))
    manifest = {"tickets/2024": {"resource_id": "r2024", "version": "2026-05-01", "rows": 1}}

    assert ckan.ingest_tickets([2024], manifest) == []


def test_ingest_tickets_keeps_bronze_when_a_new_version_has_the_same_content(tmp_path, monkeypatch):
    content = b"GRUPOSERVICO_CODIGO;SERVICO_CODIGO\n4;10\n"
    bronze_file = tmp_path / "data.parquet"
    bronze_file.write_bytes(b"existing")
    monkeypatch.setattr(ckan, "fetch_resources", lambda: [RESOURCE])
    monkeypatch.setattr(ckan, "tickets_path", lambda year: bronze_file)
    monkeypatch.setattr(ckan, "raw_path", lambda year: tmp_path / "156_2024.csv")
    monkeypatch.setattr(
        ckan, "download_file", lambda url, destination: destination.write_bytes(content)
    )
    monkeypatch.setattr(ckan, "write_bronze", lambda *_: pytest.fail("should not rewrite bronze"))
    manifest = {
        "tickets/2024": {
            "resource_id": "r2024",
            "version": "2026-03-04",
            "sha256": hashlib.sha256(content).hexdigest(),
            "rows": 1,
        }
    }

    assert ckan.ingest_tickets([2024], manifest) == []
    assert manifest["tickets/2024"]["version"] == "2026-05-01"
