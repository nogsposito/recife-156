import logging
import unicodedata
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Raw column (uppercased) -> clean column name
COLUMNS = {
    "GRUPOSERVICO_CODIGO": "group_code",
    "GRUPOSERVICO_DESCRICAO": "group_name",
    "SERVICO_CODIGO": "service_code",
    "SERVICO_DESCRICAO": "service_name",
    "LOGRADOURO": "street",
    "NUMERO": "street_number",
    "BAIRRO": "neighborhood",
    "RPA": "rpa",
    "DATA_DEMANDA": "opened_on",
    "SITUACAO": "status",
    "DATA_ULT_SITUACAO": "status_updated_on",
    "LATITUDE": "latitude",
    "LONGITUDE": "longitude",
}

UNKNOWN_NEIGHBORHOODS = {"BAIRRO NAO INFORMADO", "INDEFINIDO"}
NO_STREET_NUMBER = {"SN", "S/N", "S N"}

# Generous bounding box around Recife; points outside it are geocoding errors
LATITUDE_RANGE = (-8.20, -7.90)
LONGITUDE_RANGE = (-35.05, -34.80)

# The same ticket can appear in several yearly files, and the data has no ticket id
TICKET_KEY = ["service_code", "street", "street_number", "neighborhood", "opened_on"]


def read_raw_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=";", dtype=str, encoding="latin-1")


def _normalize_value(value: str) -> str | None:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(ascii_value.split()).upper() or None


# Uppercase, no accents and single spaces, so "Jardim  São Paulo" becomes "JARDIM SAO PAULO"
def normalize_text(series: pd.Series) -> pd.Series:
    return series.map(_normalize_value, na_action="ignore")


def clean_neighborhood(series: pd.Series) -> pd.Series:
    normalized = normalize_text(series)
    return normalized.where(~normalized.isin(UNKNOWN_NEIGHBORHOODS))


# "SN", "S/N", "0" and "00" all mean the address has no number
def clean_street_number(series: pd.Series) -> pd.Series:
    normalized = normalize_text(series)
    no_number = normalized.isin(NO_STREET_NUMBER) | normalized.str.fullmatch(r"0+", na=False)
    return normalized.where(~no_number)


def clean_coordinates(latitude: pd.Series, longitude: pd.Series) -> tuple[pd.Series, pd.Series]:
    lat = pd.to_numeric(latitude, errors="coerce")
    lon = pd.to_numeric(longitude, errors="coerce")
    inside_recife = lat.between(*LATITUDE_RANGE) & lon.between(*LONGITUDE_RANGE)
    return lat.where(inside_recife), lon.where(inside_recife)


def _to_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")


# Turns one raw yearly file into typed, standardized rows
def clean_tickets(raw: pd.DataFrame, source_year: int) -> pd.DataFrame:
    df = raw.rename(columns=lambda name: COLUMNS.get(name.strip().upper(), name))
    df = df[list(COLUMNS.values())].apply(lambda column: column.str.strip())
    df = df.mask(df == "")
    # Rows identical in the raw file are export duplicates. Rows that only become equal after
    # standardization (e.g. number "SN" vs "00") were typed separately and stay as two tickets.
    raw_duplicates = df.duplicated()
    df = df[~raw_duplicates]

    rpa = _to_int(df["rpa"])
    latitude, longitude = clean_coordinates(df["latitude"], df["longitude"])
    clean = pd.DataFrame(
        {
            "group_code": _to_int(df["group_code"]),
            "group_name": normalize_text(df["group_name"]),
            "service_code": _to_int(df["service_code"]),
            "service_name": normalize_text(df["service_name"]),
            "street": normalize_text(df["street"]),
            "street_number": clean_street_number(df["street_number"]),
            "neighborhood": clean_neighborhood(df["neighborhood"]),
            "rpa": rpa.where(rpa.between(1, 6)),
            "opened_on": _to_date(df["opened_on"]),
            "status": normalize_text(df["status"]),
            "status_updated_on": _to_date(df["status_updated_on"]),
            "latitude": latitude,
            "longitude": longitude,
            "source_year": source_year,
        }
    )

    valid = clean.dropna(subset=["group_code", "service_code", "opened_on", "status"])
    log.info(
        "%s: %d rows, %d exact duplicates, %d without required fields",
        source_year,
        len(raw),
        raw_duplicates.sum(),
        len(clean) - len(valid),
    )
    return valid


# Keeps only the latest snapshot of each ticket. Rows sharing the same key inside one file
# are treated as distinct tickets and matched across files by their order of appearance.
def deduplicate_snapshots(tickets: pd.DataFrame) -> pd.DataFrame:
    df = tickets.copy()
    df["occurrence"] = df.groupby(TICKET_KEY + ["source_year"], dropna=False).cumcount()
    df = df.sort_values("source_year", kind="stable")
    df = df.drop_duplicates(TICKET_KEY + ["occurrence"], keep="last")
    return df.drop(columns="occurrence").sort_index()


# Joins the yearly files and keeps tickets opened within the selected years
def combine_snapshots(frames: list[pd.DataFrame], years: list[int]) -> pd.DataFrame:
    stacked = pd.concat(frames, ignore_index=True)
    tickets = deduplicate_snapshots(stacked)
    in_window = tickets["opened_on"].dt.year.isin(years)
    consistent = ~(tickets["status_updated_on"] < tickets["opened_on"])
    result = tickets[in_window & consistent].reset_index(drop=True)
    log.info(
        "Combined %d rows: %d older snapshots, %d opened outside %s, %d with inconsistent dates",
        len(stacked),
        len(stacked) - len(tickets),
        (~in_window).sum(),
        years,
        (in_window & ~consistent).sum(),
    )
    log.info("Final dataset: %d tickets", len(result))
    return result
