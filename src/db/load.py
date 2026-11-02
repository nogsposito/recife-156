import io
import logging

import pandas as pd
from sqlalchemy import Engine, create_engine

from src.config import DATABASE_URL, SQL_DIR

log = logging.getLogger(__name__)


def get_engine() -> Engine:
    return create_engine(DATABASE_URL)


# COPY is much faster than row-by-row INSERTs; empty CSV fields become NULL
def copy_dataframe(cursor, table: str, df: pd.DataFrame) -> None:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    columns = ", ".join(df.columns)
    with cursor.copy(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv)") as copy:
        copy.write(buffer.getvalue())


# Recreates the schema and loads every table in a single transaction
def load_tables(tables: dict[str, pd.DataFrame]) -> None:
    schema_sql = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    with get_engine().begin() as connection:
        cursor = connection.connection.driver_connection.cursor()
        cursor.execute(schema_sql)
        for table, df in tables.items():
            copy_dataframe(cursor, table, df)
            log.info("Loaded %d rows into %s", len(df), table)
