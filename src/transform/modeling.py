import pandas as pd

TICKET_COLUMNS = [
    "service_code",
    "neighborhood_id",
    "street",
    "street_number",
    "opened_on",
    "status",
    "status_updated_on",
    "latitude",
    "longitude",
    "source_year",
]


# Splits the clean tickets into the tables of the relational model (sql/schema.sql)
def build_tables(tickets: pd.DataFrame) -> dict[str, pd.DataFrame]:
    latest_first = tickets.sort_values("source_year", ascending=False, kind="stable")
    groups = latest_first.drop_duplicates("group_code")[["group_code", "group_name"]]
    services = latest_first.drop_duplicates("service_code")[
        ["service_code", "service_name", "group_code"]
    ]

    # A few rows carry a wrong RPA, so each neighborhood takes its most frequent one
    neighborhoods = (
        tickets.dropna(subset=["neighborhood", "rpa"])
        .groupby("neighborhood")["rpa"]
        .agg(lambda rpa: rpa.mode().iloc[0])
        .reset_index()
        .rename(columns={"neighborhood": "neighborhood_name"})
    )
    neighborhoods.insert(0, "neighborhood_id", range(1, len(neighborhoods) + 1))

    neighborhood_ids = neighborhoods.set_index("neighborhood_name")["neighborhood_id"]
    fact = tickets.assign(
        neighborhood_id=tickets["neighborhood"].map(neighborhood_ids).astype("Int64"),
        opened_on=tickets["opened_on"].dt.date,
        status_updated_on=tickets["status_updated_on"].dt.date,
    )
    return {
        "service_groups": groups.sort_values("group_code"),
        "services": services.sort_values("service_code"),
        "neighborhoods": neighborhoods,
        "tickets": fact[TICKET_COLUMNS],
    }
