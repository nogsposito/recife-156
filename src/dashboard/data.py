import pandas as pd
import streamlit as st
from sqlalchemy import Engine, text

from src.config import SQL_DIR
from src.db.load import get_engine

AGE_BUCKETS = ["Até 30 dias", "31 a 180 dias", "Mais de 180 dias"]


@st.cache_resource
def _engine() -> Engine:
    return get_engine()


def _read(sql: str) -> pd.DataFrame:
    with _engine().connect() as connection:
        return pd.read_sql(text(sql), connection)


# About 200 thousand rows, small enough to load once and filter in memory on every page
@st.cache_data(ttl=3600)
def load_tickets() -> pd.DataFrame:
    tickets = _read("SELECT * FROM v_tickets")
    for column in ("opened_on", "status_updated_on"):
        tickets[column] = pd.to_datetime(tickets[column])
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


# Empty selections mean "all", so the pages start with the whole city
def sidebar_filters(tickets: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        groups = st.multiselect(
            "Grupo de serviço", sorted(tickets["group_name"].unique()), placeholder="Todos"
        )
        rpas = st.multiselect("RPA", list(range(1, 7)), placeholder="Todas")
    mask = pd.Series(True, index=tickets.index)
    if groups:
        mask &= tickets["group_name"].isin(groups)
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


def fmt_pct(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")
