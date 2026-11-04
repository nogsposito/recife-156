import json

import pandas as pd
import streamlit as st
from sqlalchemy import Engine, text

from src.config import DOCS_DIR, SQL_DIR
from src.dashboard.labels import place_label, sentence_label
from src.db.load import get_engine
from src.ml.predict import load_artifact

AGE_BUCKETS = ["Até 30 dias", "31 a 180 dias", "Mais de 180 dias"]


@st.cache_resource
def _engine() -> Engine:
    return get_engine()


def _read(sql: str, **params) -> pd.DataFrame:
    with _engine().connect() as connection:
        return pd.read_sql(text(sql), connection, params=params)


def _labels(names: pd.Series, label) -> pd.Series:
    mapping = {name: label(name) for name in names.dropna().unique()}
    return names.map(mapping).astype("category")


# About 200 thousand rows, small enough to load once and filter in memory on every page
@st.cache_data(ttl=3600)
def load_tickets() -> pd.DataFrame:
    tickets = _read("SELECT * FROM v_tickets")
    for column in ("opened_on", "status_updated_on"):
        tickets[column] = pd.to_datetime(tickets[column])
    tickets["group"] = _labels(tickets["group_name"], sentence_label)
    tickets["service"] = _labels(tickets["service_name"], sentence_label)
    tickets["neighborhood"] = _labels(tickets["neighborhood_name"], place_label)
    return tickets


@st.cache_data(ttl=3600)
def load_rain() -> pd.DataFrame:
    rain = _read("SELECT date_key, precipitation_mm FROM dim_date")
    rain["date_key"] = pd.to_datetime(rain["date_key"])
    return rain


@st.cache_data(ttl=3600)
def load_daily_tickets_and_rain() -> pd.DataFrame:
    sql = (SQL_DIR / "analyses" / "09_daily_tickets_and_rain.sql").read_text(encoding="utf-8")
    return _read(sql)


@st.cache_resource
def load_model() -> dict | None:
    return load_artifact(engine=_engine())


@st.cache_data(ttl=600)
def load_pipeline_runs() -> pd.DataFrame:
    return _read("SELECT * FROM ops.pipeline_runs ORDER BY run_id DESC LIMIT 15")


@st.cache_data(ttl=600)
def load_quality_checks(run_id: int) -> pd.DataFrame:
    return _read(
        "SELECT check_name, severity, passed, details FROM ops.quality_checks "
        "WHERE run_id = :run_id ORDER BY severity, check_name",
        run_id=run_id,
    )


@st.cache_data(ttl=600)
def load_layer_sizes() -> dict[str, int]:
    tables = ["fact_tickets", "dim_service", "dim_neighborhood", "dim_date"]
    counts = _read(" UNION ALL ".join(f"SELECT '{t}' AS t, COUNT(*) AS n FROM {t}" for t in tables))
    return dict(zip(counts["t"], counts["n"], strict=True))


@st.cache_data(ttl=600)
def load_source_versions(run_id: int) -> pd.DataFrame:
    return _read(
        "SELECT source, version, sha256, rows, ingested_at FROM ops.source_versions "
        "WHERE run_id = :run_id ORDER BY source",
        run_id=run_id,
    )


# Results written by `make nlp` and `make benchmark`, versioned in docs/
@st.cache_data
def load_doc_json(name: str) -> dict | None:
    path = DOCS_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@st.cache_data
def load_service_mapping() -> pd.DataFrame:
    return pd.read_csv(DOCS_DIR / "service_mapping.csv")


# Empty selections mean "all", so the pages start with the whole city
def sidebar_filters(tickets: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        groups = st.multiselect(
            "Grupo de serviço", sorted(tickets["group"].dropna().unique()), placeholder="Todos"
        )
        rpas = st.multiselect("RPA", list(range(1, 7)), placeholder="Todas")
    mask = pd.Series(True, index=tickets.index)
    if groups:
        mask &= tickets["group"].isin(groups)
    if rpas:
        mask &= tickets["rpa"].isin(rpas)
    return tickets[mask]


def open_with_age(tickets: pd.DataFrame, reference: pd.Timestamp) -> pd.DataFrame:
    open_tickets = tickets[tickets["is_open"]].copy()
    open_tickets["age_days"] = (reference - open_tickets["opened_on"]).dt.days
    open_tickets["age_bucket"] = pd.cut(
        open_tickets["age_days"], [-1, 30, 180, float("inf")], labels=AGE_BUCKETS
    )
    return open_tickets


def fmt_int(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def fmt_pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%".replace(".", ",")


def fmt_num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")
