import json
import logging
import os
import warnings
from collections import Counter
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from src.config import DOCS_DIR
from src.ingestion.ckan import ingest
from src.transform.cleaning import normalize_text, read_raw_csv

log = logging.getLogger("nlp")

CURRENT_YEARS = [2024, 2025]
HISTORIC_YEARS = list(range(2012, 2024))
# Multilingual sentence-transformer, small enough to run on CPU
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Names used by fewer tickets than this in a year are mostly typos or broken CSV lines
MIN_TICKETS = 5
REPORT_PATH = DOCS_DIR / "nlp_results.md"
MAPPING_PATH = DOCS_DIR / "service_mapping.csv"
RESULTS_PATH = DOCS_DIR / "nlp_results.json"
START_MARK, END_MARK = "<!-- nlp:start -->", "<!-- nlp:end -->"


# One row per year, group and service name, with how many tickets used that combination
def service_catalog(years: list[int]) -> pd.DataFrame:
    frames = []
    for year, path in zip(years, ingest(years), strict=True):
        raw = read_raw_csv(path)
        names = pd.DataFrame(
            {
                "group_raw": normalize_text(raw["GRUPOSERVICO_DESCRICAO"]),
                "service": normalize_text(raw["SERVICO_DESCRICAO"]),
            }
        )
        counts = names.value_counts().rename("tickets").reset_index().assign(year=year)
        frames.append(counts[counts["tickets"] >= MIN_TICKETS])
    return pd.concat(frames, ignore_index=True)


def _is_subsequence(short: str, long: str) -> bool:
    letters = iter(long)
    return all(char in letters for char in short)


# Files up to 2023 dropped every accented letter ("ILUMINAO PBLICA"), so an old group name is
# matched to the current group that contains it letter by letter, with only a few letters lost
def match_group(old: str, current_groups: list[str], max_lost_letters: int = 4) -> str | None:
    compact = old.replace(" ", "")
    candidates = [
        group
        for group in current_groups
        if _is_subsequence(compact, group.replace(" ", ""))
        and len(group.replace(" ", "")) - len(compact) <= max_lost_letters
    ]
    return min(candidates, key=len) if candidates else None


# The same loss of accented letters breaks words inside service names ("MANUTENO EM LMPADA").
# Each unknown word is restored to the most common current word that contains it letter by
# letter and starts with the same letter ("MANUTENCAO EM LAMPADA").
def repair_text(text: str, vocabulary: Counter, max_lost_letters: int = 3) -> str:
    words = []
    for word in text.split():
        candidates = [
            known
            for known in vocabulary
            if word not in vocabulary
            and known[0] == word[0]
            and 0 < len(known) - len(word) <= max_lost_letters
            and _is_subsequence(word, known)
        ]
        words.append(max(candidates, key=vocabulary.get) if candidates else word)
    return " ".join(words)


# Train: current names and groups. Test: historic names never used in the current files,
# labeled with their own group translated to the current taxonomy.
def build_datasets(catalog: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    current = catalog[catalog["year"].isin(CURRENT_YEARS)]
    train = (
        current.groupby(["service", "group_raw"], as_index=False)["tickets"]
        .sum()
        .rename(columns={"group_raw": "group"})
    )
    groups = sorted(train["group"].unique())
    historic = catalog[catalog["year"].isin(HISTORIC_YEARS)].copy()
    historic["group"] = historic["group_raw"].map(lambda name: match_group(name, groups))
    test = (
        historic.dropna(subset=["group"])
        .groupby(["service", "group"], as_index=False)
        .agg(tickets=("tickets", "sum"), first_year=("year", "min"), last_year=("year", "max"))
    )
    test = test[~test["service"].isin(train["service"])].reset_index(drop=True)
    vocabulary = Counter(word for name in train["service"] for word in name.split())
    test["service_repaired"] = test["service"].map(lambda name: repair_text(name, vocabulary))
    return train, test


@lru_cache(maxsize=1)
def _embedding_model():
    # Download and loading progress bars would flood the notebook output
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    warnings.filterwarnings("ignore", message="IProgress not found")
    # Imported here so the rest of the project and its tests do not need PyTorch
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def embed(texts: list[str]) -> np.ndarray:
    return _embedding_model().encode(
        [t.lower() for t in texts],
        normalize_embeddings=True,
        batch_size=64,
        show_progress_bar=False,
    )


# ticket_accuracy weighs each description by how many tickets used it: the share of the
# historic tickets that would land in the right group
def _metrics(y_true: pd.Series, y_pred: np.ndarray, tickets: pd.Series) -> dict[str, float]:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "ticket_accuracy": accuracy_score(y_true, y_pred, sample_weight=tickets),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
    }


# Three ways of predicting the group of a historic service name, all trained on current names.
# `text` picks the test column: the name as written in the old file or the repaired one.
def evaluate(train: pd.DataFrame, test: pd.DataFrame, text: str = "service") -> dict:
    classifier = LogisticRegression(max_iter=5000, class_weight="balanced", C=10)

    tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    tfidf_pred = classifier.fit(tfidf.fit_transform(train["service"]), train["group"]).predict(
        tfidf.transform(test[text])
    )

    vectors = embed(list(train["service"]) + list(test[text]))
    train_vectors, test_vectors = vectors[: len(train)], vectors[len(train) :]
    embedding_pred = classifier.fit(train_vectors, train["group"]).predict(test_vectors)

    # Nearest current service by cosine similarity: also the suggested mapping old -> current
    similarity = test_vectors @ train_vectors.T
    nearest = similarity.argmax(axis=1)
    neighbor_pred = train["group"].to_numpy()[nearest]

    predictions = {
        "Caracteres (TF-IDF) + regressão logística": tfidf_pred,
        "Embeddings (transformer) + regressão logística": embedding_pred,
        "Embeddings: serviço atual mais parecido": neighbor_pred,
    }
    mapping = test.assign(
        suggested_service=train["service"].to_numpy()[nearest],
        suggested_group=neighbor_pred,
        similarity=similarity.max(axis=1).round(3),
    ).sort_values("tickets", ascending=False)

    scores = {
        name: _metrics(test["group"], pred, test["tickets"]) for name, pred in predictions.items()
    }
    best = max(scores, key=lambda name: scores[name]["f1_macro"])
    labels = sorted(test["group"].unique())
    return {
        "results": scores,
        "best": best,
        "confusion": pd.DataFrame(
            confusion_matrix(test["group"], predictions[best], labels=labels),
            index=labels,
            columns=labels,
        ),
        "mapping": mapping,
        "sizes": {"train": len(train), "test": len(test)},
    }


def _num(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


# `runs` maps a label of the test text ("original", "com reparo") to its evaluation
def results_markdown(runs: dict[str, dict]) -> str:
    sizes = next(iter(runs.values()))["sizes"]
    lines = [
        f"Treino: {sizes['train']} descrições de 2024 e 2025. Teste: {sizes['test']} "
        "descrições de 2012 a 2023 que não existem nos arquivos atuais.",
        "",
        "| Texto do teste | Método | Acurácia | Chamados no grupo certo | F1 macro "
        "| F1 ponderado |",
        "|---|---|---|---|---|---|",
    ]
    for label, run in runs.items():
        for name, m in run["results"].items():
            lines.append(
                f"| {label} | {name} | {_num(m['accuracy'])} | {_num(m['ticket_accuracy'])} | "
                f"{_num(m['f1_macro'])} | "
                f"{_num(m['f1_weighted'])} |"
            )
    return "\n".join(lines)


def save(runs: dict[str, dict]) -> None:
    runs["com reparo"]["mapping"].to_csv(MAPPING_PATH, index=False)
    results = {label: run["results"] for label, run in runs.items()}
    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report = REPORT_PATH.read_text(encoding="utf-8")
    start, end = report.index(START_MARK) + len(START_MARK), report.index(END_MARK)
    REPORT_PATH.write_text(
        report[:start] + "\n" + results_markdown(runs) + "\n" + report[end:], encoding="utf-8"
    )
    log.info("Results written to %s and %s", REPORT_PATH.name, MAPPING_PATH.name)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    train, test = build_datasets(service_catalog(CURRENT_YEARS + HISTORIC_YEARS))
    runs = {
        "original": evaluate(train, test, "service"),
        "com reparo": evaluate(train, test, "service_repaired"),
    }
    for label, run in runs.items():
        for name, metrics in run["results"].items():
            log.info("%s | %s: F1 macro %.3f", label, name, metrics["f1_macro"])
    save(runs)


if __name__ == "__main__":
    main()
