import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src.config import BRONZE_DIR

MANIFEST_PATH = BRONZE_DIR / "_manifest.json"


def tickets_path(year: int) -> Path:
    return BRONZE_DIR / "tickets" / f"year={year}" / "data.parquet"


def weather_path(year: int) -> Path:
    return BRONZE_DIR / "weather" / f"year={year}" / "data.parquet"


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# Bronze keeps the source content as it came, plus two columns saying where and when from
def write_bronze(df: pd.DataFrame, path: Path, source: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.assign(_source=source, _ingested_at=now_utc()).to_parquet(path, index=False)
    return len(df)


def read_bronze(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


# The manifest records which version of each source is already in bronze, which is what
# lets a rerun skip everything that did not change
def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_manifest(manifest: dict, path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
