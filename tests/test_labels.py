from src.dashboard.labels import place_label, sentence_label


def test_sentence_label_restores_common_accents_and_keeps_acronyms():
    assert sentence_label("MANUTENCAO EM LAMPADA APAGADA") == "Manutenção em lâmpada apagada"
    assert sentence_label("ILUMINACAO PUBLICA") == "Iluminação pública"
    assert sentence_label("SUBSTITUICAO DE LAMPADA LED") == "Substituição de lâmpada LED"


def test_place_label_capitalizes_names_but_not_connectors():
    assert place_label("COHAB IBURA DE CIMA") == "Cohab Ibura de Cima"
    assert place_label("SAO JOSE") == "São José"
    assert place_label("DOIS IRMAOS") == "Dois Irmãos"
