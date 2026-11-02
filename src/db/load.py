import io
import logging

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from src.config import DATABASE_URL, SQL_DIR

log = logging.getLogger(__name__)


def get_engine() -> Engine:
    return create_engine(DATABASE_URL)


def _sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


# COPY is much faster than row-by-row INSERTs; empty CSV fields become NULL
def copy_dataframe(cursor, table: str, df: pd.DataFrame) -> None:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    columns = ", ".join(df.columns)
    with cursor.copy(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv)") as copy:
        copy.write(buffer.getvalue())


# Recreates the gold schema, loads every table and builds the indexes in one transaction, so
# a failed load leaves the previous gold tables untouched
def load_gold(engine: Engine, tables: dict[str, pd.DataFrame]) -> None:
    with engine.begin() as connection:
        cursor = connection.connection.driver_connection.cursor()
        cursor.execute(_sql("schema.sql"))
        for table, df in tables.items():
            copy_dataframe(cursor, table, df)
            log.info("Gold: %d rows loaded into %s", len(df), table)
        cursor.execute(_sql("indexes.sql"))
        cursor.execute("ANALYZE")


def start_run(engine: Engine, years: list[int], changed_inputs: str) -> int:
    with engine.begin() as connection:
        connection.connection.driver_connection.execute(_sql("ops.sql"))
        return connection.execute(
            text(
                "INSERT INTO ops.pipeline_runs (years, changed_inputs) "
                "VALUES (:years, :changed) RETURNING run_id"
            ),
            {"years": ",".join(map(str, years)), "changed": changed_inputs},
        ).scalar_one()


def finish_run(engine: Engine, run_id: int, status: str, **counts) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE ops.pipeline_runs SET finished_at = now(), status = :status, "
                "silver_rows = :silver_rows, gold_rows = :gold_rows, message = :message "
                "WHERE run_id = :run_id"
            ),
            {
                "run_id": run_id,
                "status": status,
                "silver_rows": counts.get("silver_rows"),
                "gold_rows": counts.get("gold_rows"),
                "message": counts.get("message"),
            },
        )


def save_quality_checks(engine: Engine, run_id: int, results: list) -> None:
    rows = [
        {
            "run_id": run_id,
            "name": result.name,
            "severity": result.severity,
            "passed": result.passed,
            "details": result.details,
        }
        for result in results
    ]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO ops.quality_checks (run_id, check_name, severity, passed, details) "
                "VALUES (:run_id, :name, :severity, :passed, :details)"
            ),
            rows,
        )
