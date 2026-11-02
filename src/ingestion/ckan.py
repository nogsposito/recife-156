import logging
from pathlib import Path

import requests

from src.config import RAW_DIR

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
