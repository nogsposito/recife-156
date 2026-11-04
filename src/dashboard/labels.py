import re

# The open data stores names in capitals without accents. These are display labels only: the
# database, the model and the assistant keep the original names.
ACCENTED = {
    "AGUA": "água",
    "ANALISE": "análise",
    "ANTONIO": "antônio",
    "AREAS": "áreas",
    "ARVORE": "árvore",
    "ARVORES": "árvores",
    "ASFALTICO": "asfáltico",
    "BONIFACIO": "bonifácio",
    "BRASILIA": "brasília",
    "CACAMBA": "caçamba",
    "CALCADAS": "calçadas",
    "CAXANGA": "caxangá",
    "CORREGO": "córrego",
    "CRITICO": "crítico",
    "DENUNCIA": "denúncia",
    "DENUNCIAS": "denúncias",
    "ESTACIONARIA": "estacionária",
    "ESTANCIA": "estância",
    "FITOSSANITARIO": "fitossanitário",
    "GRACAS": "graças",
    "HEMETERIO": "hemetério",
    "HIPODROMO": "hipódromo",
    "JIQUIA": "jiquiá",
    "JOSE": "josé",
    "LAMPADA": "lâmpada",
    "LUMINARIA": "luminária",
    "LUMINARIAS": "luminárias",
    "MUDANCA": "mudança",
    "PARALELEPIPEDO": "paralelepípedo",
    "POCO": "poço",
    "PRACA": "praça",
    "PRACAS": "praças",
    "PRE": "pré",
    "PROPRIOS": "próprios",
    "PROVISORIA": "provisória",
    "PUBLICA": "pública",
    "PUBLICAS": "públicas",
    "PUBLICO": "público",
    "PUBLICOS": "públicos",
    "RAIZES": "raízes",
    "SERVICOS": "serviços",
    "SITIO": "sítio",
    "TEJIPIO": "tejipió",
    "TOTO": "totó",
    "TRANSITO": "trânsito",
    "UNIVERSITARIA": "universitária",
    "VARZEA": "várzea",
    "VEICULO": "veículo",
}
# Word endings that are always nasal in Portuguese: ILUMINACAO, RECLAMACOES, JORDAO, IRMAOS
ENDINGS = [("CAO", "ção"), ("COES", "ções"), ("AO", "ão"), ("AOS", "ãos"), ("OES", "ões")]
CONNECTORS = {"DE", "DA", "DO", "DAS", "DOS", "E"}
ACRONYMS = {"LED", "PEV", "RPA", "EMLURB"}


def _word(word: str) -> str:
    if word in ACRONYMS:
        return word
    if word in ACCENTED:
        return ACCENTED[word]
    for ending, replacement in ENDINGS:
        if len(word) > len(ending) and word.endswith(ending):
            return word[: -len(ending)].lower() + replacement
    return word.lower()


def _words(name: str) -> list[tuple[str, str]]:
    return [(word, _word(word)) for word in re.split(r"\s+", name.strip()) if word]


# Services and groups read as a sentence: "Manutenção em lâmpada apagada"
def sentence_label(name: str) -> str:
    text = " ".join(label for _, label in _words(name))
    return text[:1].upper() + text[1:]


# Neighborhoods are proper names: "Cohab Ibura de Cima", "Várzea"
def place_label(name: str) -> str:
    words = _words(name)
    return " ".join(
        label if raw in CONNECTORS and index else label[:1].upper() + label[1:]
        for index, (raw, label) in enumerate(words)
    )
