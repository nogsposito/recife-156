import json
import logging
import os
from datetime import UTC, date, datetime

import pandas as pd
from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

from src.config import DOCS_DIR, YEARS
from src.ingestion.weather import raw_weather_path
from src.layers.bronze import load_manifest, read_bronze, tickets_path

log = logging.getLogger("nosql")

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27018")
DATABASE = "recife156_raw"
BATCH_SIZE = 10_000
REPORT_PATH = DOCS_DIR / "mongo_results.md"
START_MARK, END_MARK = "<!-- mongo:start -->", "<!-- mongo:end -->"


# One document per row of a yearly file, with the original column names and text values
def ticket_documents(bronze: pd.DataFrame, year: int) -> list[dict]:
    record_columns = [column for column in bronze.columns if not column.startswith("_")]
    records = bronze[record_columns].astype(object).where(bronze[record_columns].notna(), None)
    return [
        {
            "source_year": year,
            "source": bronze["_source"].iloc[0],
            "ingested_at": bronze["_ingested_at"].iloc[0],
            "record": record,
        }
        for record in records.to_dict("records")
    ]


# A source is loaded again only when the bronze manifest shows a different version of it
def needs_reload(manifest_entry: dict, loaded: dict | None) -> bool:
    return loaded is None or loaded.get("version") != manifest_entry


def load_tickets(db: Database, manifest: dict, years: list[int]) -> None:
    for year in years:
        key = f"tickets/{year}"
        if not needs_reload(manifest[key], db.loads.find_one({"_id": key})):
            log.info("Mongo %s: already loaded", key)
            continue
        db.raw_tickets.delete_many({"source_year": year})
        documents = ticket_documents(read_bronze(tickets_path(year)), year)
        for start in range(0, len(documents), BATCH_SIZE):
            db.raw_tickets.insert_many(documents[start : start + BATCH_SIZE], ordered=False)
        db.loads.replace_one(
            {"_id": key},
            {"version": manifest[key], "documents": len(documents), "loaded_at": _now()},
            upsert=True,
        )
        log.info("Mongo %s: %d raw rows loaded", key, len(documents))
    db.raw_tickets.create_index([("source_year", ASCENDING)])


# The Open-Meteo answer is stored whole, with its metadata and nested daily arrays
def load_weather(db: Database, manifest: dict, years: list[int]) -> None:
    for year in years:
        key = f"weather/{year}"
        entry = manifest.get(key)
        if entry is None or not needs_reload(entry, db.loads.find_one({"_id": key})):
            continue
        path = raw_weather_path(
            date.fromisoformat(entry["start"]), date.fromisoformat(entry["end"])
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        db.raw_weather.replace_one(
            {"_id": key}, {"year": year, "source": path.name, "payload": payload}, upsert=True
        )
        db.loads.replace_one({"_id": key}, {"version": entry, "loaded_at": _now()}, upsert=True)
        log.info("Mongo %s: raw JSON loaded", key)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _trimmed(field: str) -> dict:
    return {"$trim": {"input": {"$ifNull": [f"$record.{field}", ""]}}}


# How many tickets appear in two yearly files, and how their status changed between files
OVERLAP_BETWEEN_FILES = [
    {
        "$group": {
            "_id": {
                field: _trimmed(field)
                for field in ["SERVICO_CODIGO", "LOGRADOURO", "NUMERO", "BAIRRO", "DATA_DEMANDA"]
            },
            "files": {"$addToSet": "$source_year"},
            "versions": {"$push": {"year": "$source_year", "status": _trimmed("SITUACAO")}},
        }
    },
    # Two different files, not two rows with the same key inside one file
    {"$match": {"files.1": {"$exists": True}}},
    {"$project": {"versions": {"$sortArray": {"input": "$versions", "sortBy": {"year": 1}}}}},
    {
        "$group": {
            "_id": {
                "status_before": {"$first": "$versions.status"},
                "status_after": {"$last": "$versions.status"},
            },
            "tickets": {"$sum": 1},
        }
    },
    {"$sort": {"tickets": -1}},
    {"$limit": 6},
]

# Share of raw rows that came with coordinates, per yearly file
COORDINATES_BY_FILE = [
    {
        "$group": {
            "_id": "$source_year",
            "rows": {"$sum": 1},
            "with_coordinates": {
                "$sum": {"$cond": [{"$gt": [{"$strLenCP": _trimmed("latitude")}, 0]}, 1, 0]}
            },
        }
    },
    {
        "$project": {
            "rows": 1,
            "with_coordinates": 1,
            "pct": {
                "$round": [{"$multiply": [{"$divide": ["$with_coordinates", "$rows"]}, 100]}, 1]
            },
        }
    },
    {"$sort": {"_id": 1}},
]

# Monthly rain from the raw JSON: the parallel daily arrays are zipped into pairs and unwound
RAIN_BY_MONTH = [
    {
        "$project": {
            "day": {"$zip": {"inputs": ["$payload.daily.time", "$payload.daily.precipitation_sum"]}}
        }
    },
    {"$unwind": "$day"},
    {
        "$group": {
            "_id": {"$substrCP": [{"$arrayElemAt": ["$day", 0]}, 0, 7]},
            "rain_mm": {"$sum": {"$arrayElemAt": ["$day", 1]}},
            "days_over_10mm": {
                "$sum": {"$cond": [{"$gte": [{"$arrayElemAt": ["$day", 1]}, 10]}, 1, 0]}
            },
        }
    },
    {"$project": {"rain_mm": {"$round": ["$rain_mm", 1]}, "days_over_10mm": 1}},
    {"$sort": {"_id": 1}},
]


def run_aggregations(db: Database) -> dict[str, pd.DataFrame]:
    results = {
        "overlap": db.raw_tickets.aggregate(OVERLAP_BETWEEN_FILES, allowDiskUse=True),
        "coordinates": db.raw_tickets.aggregate(COORDINATES_BY_FILE),
        "rain": db.raw_weather.aggregate(RAIN_BY_MONTH),
    }
    return {name: pd.json_normalize(list(cursor)) for name, cursor in results.items()}


def _markdown_table(df: pd.DataFrame) -> str:
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def results_markdown(results: dict[str, pd.DataFrame]) -> str:
    overlap = results["overlap"].rename(
        columns={
            "_id.status_before": "Situação no arquivo mais antigo",
            "_id.status_after": "Situação no mais novo",
            "tickets": "Chamados",
        }
    )
    coordinates = results["coordinates"].rename(
        columns={
            "_id": "Arquivo",
            "rows": "Linhas",
            "with_coordinates": "Com coordenadas",
            "pct": "%",
        }
    )
    rain = results["rain"].rename(
        columns={"_id": "Mês", "rain_mm": "Chuva (mm)", "days_over_10mm": "Dias acima de 10 mm"}
    )
    sections = [
        ("Mesmo chamado em dois arquivos anuais (as 6 mudanças de situação mais comuns)", overlap),
        ("Linhas brutas com coordenadas, por arquivo", coordinates),
        ("Chuva por mês, a partir do JSON bruto do clima", rain),
    ]
    return "\n\n".join(f"{title}:\n\n{_markdown_table(table)}" for title, table in sections)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db = MongoClient(MONGO_URL)[DATABASE]
    manifest = load_manifest()
    load_tickets(db, manifest, YEARS)
    load_weather(db, manifest, YEARS)
    report = REPORT_PATH.read_text(encoding="utf-8")
    start, end = report.index(START_MARK) + len(START_MARK), report.index(END_MARK)
    tables = results_markdown(run_aggregations(db))
    REPORT_PATH.write_text(report[:start] + "\n" + tables + "\n" + report[end:], encoding="utf-8")
    log.info("Aggregations written to %s", REPORT_PATH.name)


if __name__ == "__main__":
    main()
