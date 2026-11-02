import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SQL_DIR = PROJECT_ROOT / "sql"
DOCS_DIR = PROJECT_ROOT / "docs"

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://recife:recife@localhost:5433/recife156"
)

# Files before 2024 use another coding scheme for services and have accents stripped
FIRST_SUPPORTED_YEAR = 2024


def parse_years(value: str) -> list[int]:
    years = sorted({int(year) for year in value.split(",") if year.strip()})
    if not years or years[0] < FIRST_SUPPORTED_YEAR:
        raise ValueError(f"YEARS must list years from {FIRST_SUPPORTED_YEAR} on, got {value!r}")
    return years


YEARS = parse_years(os.getenv("YEARS", "2024,2025"))
