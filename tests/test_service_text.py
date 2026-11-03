from collections import Counter

import pandas as pd

from src.nlp.service_text import build_datasets, match_group, repair_text

CURRENT = ["ILUMINACAO PUBLICA", "LIMPEZA URBANA", "PLANEJAMENTO DE LIMPEZA URBANA", "PRACAS"]


def test_match_group_recovers_names_that_lost_their_accented_letters():
    assert match_group("ILUMINAO PBLICA", CURRENT) == "ILUMINACAO PUBLICA"
    assert match_group("PRAAS", CURRENT) == "PRACAS"


def test_match_group_prefers_the_closest_name_and_rejects_unrelated_ones():
    assert match_group("LIMPEZA URBANA", CURRENT) == "LIMPEZA URBANA"
    assert match_group("NECROPOLES", CURRENT) is None


def test_build_datasets_tests_only_on_historic_names_unseen_in_current_files():
    catalog = pd.DataFrame(
        {
            "group_raw": ["ILUMINACAO PUBLICA", "ILUMINAO PBLICA", "ILUMINAO PBLICA", "NECROPOLES"],
            "service": ["LAMPADA APAGADA", "LAMPADA APAGADA", "LUMINARIA QUEBRADA", "CEMITERIO"],
            "tickets": [100, 40, 20, 10],
            "year": [2025, 2020, 2021, 2019],
        }
    )

    train, test = build_datasets(catalog)

    assert train["service"].tolist() == ["LAMPADA APAGADA"]
    # The repeated name is already known, and the cemetery group has no current equivalent
    assert test[["service", "group"]].values.tolist() == [
        ["LUMINARIA QUEBRADA", "ILUMINACAO PUBLICA"]
    ]


def test_repair_text_restores_words_that_lost_accented_letters():
    vocabulary = Counter(["MANUTENCAO", "EM", "LAMPADA", "APAGADA", "MANUTENCAO", "REMOCAO"])

    assert repair_text("MANUTENO EM LMPADA APAGADA", vocabulary) == "MANUTENCAO EM LAMPADA APAGADA"
    assert repair_text("PODA EXTRA", vocabulary) == "PODA EXTRA"
