import io
import logging
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.config import DOCS_DIR, PROJECT_ROOT
from src.db.load import get_engine, save_model_artifact
from src.ml.features import (
    CATEGORICAL,
    FEATURES,
    HORIZON_DAYS,
    TemporalSplit,
    build_features,
    build_target,
    load_model_data,
    outcome_is_known,
    temporal_split,
    to_model_input,
)

log = logging.getLogger("train")

MODEL_PATH = PROJECT_ROOT / "models" / "resolution_30d.joblib"
MODEL_NAME = MODEL_PATH.stem
REPORT_PATH = DOCS_DIR / "ml_results.md"
START_MARK, END_MARK = "<!-- ml:start -->", "<!-- ml:end -->"
RANDOM_STATE = 42


def make_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        categorical_features="from_dtype",
        learning_rate=0.08,
        max_iter=300,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=RANDOM_STATE,
    )


# Metrics from the point of view of the alert the model raises: "this ticket will probably
# not be resolved within 30 days" (predicted chance below 50%)
def evaluate(y_true: pd.Series, chance: np.ndarray) -> dict[str, float]:
    late, alert = 1 - y_true, (chance < 0.5).astype(int)
    return {
        "auc": roc_auc_score(y_true, chance),
        "brier": brier_score_loss(y_true, chance),
        "accuracy": accuracy_score(y_true, chance >= 0.5),
        "alert_precision": precision_score(late, alert, zero_division=0),
        "alert_recall": recall_score(late, alert, zero_division=0),
    }


# Mean predicted chance against the share actually resolved, in ten bins of predicted chance
def calibration_table(y_true: pd.Series, chance: np.ndarray) -> pd.DataFrame:
    frame = pd.DataFrame({"predicted": chance, "observed": y_true.to_numpy()})
    frame["bin"] = pd.cut(frame["predicted"], np.linspace(0, 1, 11), include_lowest=True)
    return (
        frame.groupby("bin", observed=True)
        .agg(
            predicted=("predicted", "mean"), observed=("observed", "mean"), tickets=("bin", "size")
        )
        .reset_index(drop=True)
    )


# Brier score of the service history and of the model inside each service group
def error_by_group(
    groups: pd.Series, y_true: pd.Series, history: np.ndarray, chance: np.ndarray
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "group": groups.to_numpy(),
            "history": (history - y_true.to_numpy()) ** 2,
            "model": (chance - y_true.to_numpy()) ** 2,
        }
    )
    return (
        frame.groupby("group")
        .agg(
            tickets=("model", "size"),
            history_brier=("history", "mean"),
            model_brier=("model", "mean"),
        )
        .reset_index()
    )


# Fits two baselines and the model on the past and scores all three on the test months
def fit_and_evaluate(tickets: pd.DataFrame, rain: pd.DataFrame, split: TemporalSplit) -> dict:
    features = build_features(tickets, rain)
    target = build_target(tickets)
    reference = tickets["status_updated_on"].max()
    known = outcome_is_known(tickets, reference)
    train = known & (tickets["opened_on"] <= split.train_end)
    test = known & tickets["opened_on"].between(split.test_start, split.test_end)

    categories = {
        column: sorted(features.loc[train, column].dropna().unique()) for column in CATEGORICAL
    }
    x_train = to_model_input(features[train], categories)
    x_test = to_model_input(features[test], categories)
    y_train, y_test = target[train], target[test]

    global_rate = y_train.mean()
    service_rates = y_train.groupby(features.loc[train, "service_name"]).mean()
    baselines = {
        "Taxa geral do treino": np.full(len(y_test), global_rate),
        "Histórico do serviço": features.loc[test, "service_name"]
        .map(service_rates)
        .fillna(global_rate)
        .to_numpy(),
    }

    model = make_model().fit(x_train, y_train)
    model_chance = model.predict_proba(x_test)[:, 1]
    results = {name: evaluate(y_test, chance) for name, chance in baselines.items()}
    results["Gradient boosting"] = evaluate(y_test, model_chance)
    for name, metrics in results.items():
        log.info("%s: AUC %.3f, Brier %.3f", name, metrics["auc"], metrics["brier"])

    # How much the AUC drops when each feature is shuffled, on a sample of the test months
    sample = x_test.sample(min(len(x_test), 20_000), random_state=RANDOM_STATE)
    importance = permutation_importance(
        model,
        sample,
        y_test.loc[sample.index],
        scoring="roc_auc",
        n_repeats=5,
        random_state=RANDOM_STATE,
    )
    importances = pd.Series(importance.importances_mean, index=FEATURES).sort_values(
        ascending=False
    )

    return {
        "model": model,
        "categories": categories,
        "service_rates": service_rates,
        "global_rate": global_rate,
        "split": split,
        "reference_date": reference,
        "sizes": {"train": int(train.sum()), "test": int(test.sum())},
        "positive_rate": {"train": float(y_train.mean()), "test": float(y_test.mean())},
        "results": results,
        "importances": importances,
        "calibration": calibration_table(y_test, model_chance),
        "error_by_group": error_by_group(
            features.loc[test, "group_name"],
            y_test,
            baselines["Histórico do serviço"],
            model_chance,
        ),
        "test_frame": features[test].assign(**{"actual": y_test, "model_chance": model_chance}),
    }


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%".replace(".", ",")


def _int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _num(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def results_markdown(run: dict) -> str:
    split = run["split"]
    sizes, rates = run["sizes"], run["positive_rate"]
    lines = [
        f"Treino: chamados abertos até {split.train_end:%d/%m/%Y} ({_int(sizes['train'])} "
        f"chamados, {_pct(rates['train'])} atendidos em até {HORIZON_DAYS} dias).",
        f"Teste: chamados abertos de {split.test_start:%d/%m/%Y} a {split.test_end:%d/%m/%Y} "
        f"({_int(sizes['test'])} chamados, {_pct(rates['test'])} atendidos em até "
        f"{HORIZON_DAYS} dias).",
        "",
        "| Modelo | AUC | Brier | Acurácia | Precisão do alerta | Recall do alerta |",
        "|---|---|---|---|---|---|",
    ]
    for name, m in run["results"].items():
        lines.append(
            f"| {name} | {_num(m['auc'])} | {_num(m['brier'])} | {_pct(m['accuracy'])} | "
            f"{_pct(m['alert_precision'])} | {_pct(m['alert_recall'])} |"
        )
    lines += ["", "| Variável | Queda da AUC ao embaralhar |", "|---|---|"]
    for feature, drop in run["importances"].items():
        lines.append(f"| `{feature}` | {_num(drop, 4)} |")
    return "\n".join(lines)


def save(run: dict) -> None:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    artifact = {key: value for key, value in run.items() if key != "test_frame"}
    artifact["trained_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    joblib.dump(artifact, MODEL_PATH)
    buffer = io.BytesIO()
    joblib.dump(artifact, buffer, compress=3)
    save_model_artifact(get_engine(), MODEL_NAME, buffer.getvalue())
    log.info("Model saved to %s and to ops.model_artifacts", MODEL_PATH)

    report = REPORT_PATH.read_text(encoding="utf-8")
    start, end = report.index(START_MARK) + len(START_MARK), report.index(END_MARK)
    report = report[:start] + "\n" + results_markdown(run) + "\n" + report[end:]
    REPORT_PATH.write_text(report, encoding="utf-8")
    log.info("Results written to %s", REPORT_PATH)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    tickets, rain = load_model_data(get_engine())
    split = temporal_split(tickets["status_updated_on"].max())
    log.info(
        "Train until %s, test %s to %s",
        split.train_end.date(),
        split.test_start.date(),
        split.test_end.date(),
    )
    save(fit_and_evaluate(tickets, rain, split))


if __name__ == "__main__":
    main()
