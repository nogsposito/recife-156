import logging
from pathlib import Path

import requests

from src.config import RAW_DIR
from src.layers.bronze import file_sha256, now_utc, tickets_path, write_bronze
from src.transform.cleaning import read_raw_csv

log = logging.getLogger(__name__)

CKAN_PACKAGE_URL = "https://dados.recife.pe.gov.br/api/3/action/package_show"
DATASET_ID = "central-de-atendimento-de-servicos-da-emlurb-156"


def fetch_resources() -> list[dict]:
    response = requests.get(CKAN_PACKAGE_URL, params={"id": DATASET_ID}, timeout=30)
    response.raise_for_status()
    return response.json()["result"]["resources"]


def _modified_at(resource: dict) -> str:
    return resource.get("last_modified") or resource.get("created") or ""


# The portal lists some years twice; keep the most recently modified CSV of each year
def pick_latest_per_year(resources: list[dict]) -> dict[int, dict]:
    latest: dict[int, dict] = {}
    for resource in resources:
        prefix = resource["name"][:4]
        if resource.get("format", "").upper() != "CSV" or not prefix.isdigit():
            continue
        year = int(prefix)
        if year not in latest or _modified_at(resource) > _modified_at(latest[year]):
            latest[year] = resource
    return latest


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(".part")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(tmp_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1 << 20):
                file.write(chunk)
    tmp_path.replace(destination)


def raw_path(year: int) -> Path:
    return RAW_DIR / f"156_{year}.csv"


# Downloads one CSV per requested year; files already on disk are reused unless force=True
def ingest(years: list[int], force: bool = False) -> list[Path]:
    paths = [raw_path(year) for year in years]
    if not force and all(path.exists() for path in paths):
        log.info("Raw files already downloaded for %s", years)
        return paths

    available = pick_latest_per_year(fetch_resources())
    missing = [year for year in years if year not in available]
    if missing:
        raise ValueError(f"Years not available on the portal: {missing}")

    for year, path in zip(years, paths, strict=True):
        if path.exists() and not force:
            log.info("%s: using cached file %s", year, path.name)
            continue
        resource = available[year]
        log.info("%s: downloading resource %s", year, resource["id"])
        download_file(resource["url"], path)
    return paths


# Brings each year's CSV into bronze. A year is skipped when the portal still lists the same
# version already ingested, and also when a new version has exactly the same content.
def ingest_tickets(years: list[int], manifest: dict, force: bool = False) -> list[int]:
    try:
        available = pick_latest_per_year(fetch_resources())
    except requests.RequestException as error:
        if not force and all(tickets_path(year).exists() for year in years):
            log.warning("Portal unreachable (%s); keeping the current bronze files", error)
            return []
        raise
    missing = [year for year in years if year not in available]
    if missing:
        raise ValueError(f"Years not available on the portal: {missing}")

    changed = []
    for year in years:
        resource, key = available[year], f"tickets/{year}"
        saved = manifest.get(key, {})
        version = _modified_at(resource)
        same_version = (
            saved.get("resource_id") == resource["id"] and saved.get("version") == version
        )
        if same_version and tickets_path(year).exists() and not force:
            log.info("%s: unchanged on the portal, bronze kept", year)
            continue

        landing = raw_path(year)
        download_file(resource["url"], landing)
        sha256 = file_sha256(landing)
        if saved.get("sha256") == sha256 and tickets_path(year).exists() and not force:
            log.info("%s: new version on the portal with identical content", year)
            rows = saved["rows"]
        else:
            rows = write_bronze(read_raw_csv(landing), tickets_path(year), resource["url"])
            log.info("%s: %d rows written to bronze", year, rows)
            changed.append(year)
        manifest[key] = {
            "resource_id": resource["id"],
            "version": version,
            "sha256": sha256,
            "rows": rows,
            "ingested_at": now_utc(),
        }
    return changed
