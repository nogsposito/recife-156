import pandas as pd

from src.transform.cleaning import (
    clean_coordinates,
    clean_neighborhood,
    clean_tickets,
    deduplicate_snapshots,
    normalize_text,
)


def raw_row(**overrides) -> dict:
    row = {
        "GRUPOSERVICO_CODIGO": "4",
        "GRUPOSERVICO_DESCRICAO": "ILUMINACAO PUBLICA",
        "SERVICO_CODIGO": "10",
        "SERVICO_DESCRICAO": "MANUTENCAO EM LAMPADA APAGADA",
        "LOGRADOURO": "RUA  do Chacon",
        "NUMERO": "65                  ",
        "BAIRRO": "Jardim Sao Paulo",
        "RPA": "5",
        "DATA_DEMANDA": "2024-08-03",
        "SITUACAO": "ATENDIDA",
        "DATA_ULT_SITUACAO": "2024-08-05",
        "latitude": "-8.0852089",
        "longitude": "-34.9490991",
    }
    return row | overrides


def test_normalize_text_removes_accents_case_and_extra_spaces():
    result = normalize_text(pd.Series(["  Jardim   São Paulo ", "Várzea", None]))
    assert result.tolist()[:2] == ["JARDIM SAO PAULO", "VARZEA"]
    assert pd.isna(result.iloc[2])


def test_clean_neighborhood_turns_placeholders_into_missing():
    result = clean_neighborhood(pd.Series(["BAIRRO NAO INFORMADO", "Indefinido", "Boa Viagem"]))
    assert result.isna().tolist() == [True, True, False]


def test_clean_coordinates_drops_points_outside_recife():
    lat, lon = clean_coordinates(
        pd.Series(["-8.05", "85.05", "abc"]), pd.Series(["-34.90", "-180", "-34.9"])
    )
    assert lat.iloc[0] == -8.05 and lon.iloc[0] == -34.90
    assert lat.iloc[1:].isna().all() and lon.iloc[1:].isna().all()


def test_clean_tickets_types_columns_and_drops_rows_without_required_fields():
    raw = pd.DataFrame([raw_row(), raw_row(DATA_DEMANDA="not a date"), raw_row(NUMERO="SN")])
    clean = clean_tickets(raw, source_year=2024)

    assert len(clean) == 2
    first = clean.iloc[0]
    assert first.street == "RUA DO CHACON"
    assert first.street_number == "65"
    assert first.neighborhood == "JARDIM SAO PAULO"
    assert first.opened_on == pd.Timestamp("2024-08-03")
    assert first.service_code == 10 and first.rpa == 5
    assert pd.isna(clean.iloc[1].street_number)


def test_deduplicate_snapshots_keeps_latest_status_of_each_ticket():
    older = clean_tickets(pd.DataFrame([raw_row(SITUACAO="EXECUCAO")]), source_year=2024)
    newer = clean_tickets(pd.DataFrame([raw_row(DATA_ULT_SITUACAO="2025-02-10")]), source_year=2025)
    # The 2024 file had two tickets with the same key; only one of them shows up again in 2025
    older = pd.concat([older, older], ignore_index=True)

    result = deduplicate_snapshots(pd.concat([older, newer], ignore_index=True))

    assert len(result) == 2
    assert sorted(result.status) == ["ATENDIDA", "EXECUCAO"]
    assert result[result.status == "ATENDIDA"].source_year.item() == 2025
