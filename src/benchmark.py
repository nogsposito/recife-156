import json
import logging
import statistics
from pathlib import Path

from sqlalchemy import Connection, text

from src.config import DOCS_DIR, SQL_DIR
from src.db.load import get_engine

log = logging.getLogger("benchmark")

# Timed without and with the indexes of sql/indexes.sql
QUERIES = [
    SQL_DIR / "benchmark" / "01_open_queue_by_neighborhood.sql",
    SQL_DIR / "benchmark" / "02_service_moving_average.sql",
    SQL_DIR / "analyses" / "09_daily_tickets_and_rain.sql",
]
# Same result, different SQL: (first version, rewritten version), timed with the indexes on
REWRITES = [
    (
        SQL_DIR / "benchmark" / "03_daily_tickets_and_rain_join_first.sql",
        SQL_DIR / "analyses" / "09_daily_tickets_and_rain.sql",
    )
]
INDEXES = ["idx_fact_tickets_service_opened", "idx_fact_tickets_open_by_neighborhood"]
RUNS = 15
REPORT_PATH = DOCS_DIR / "sql_optimization.md"
RESULTS_PATH = DOCS_DIR / "benchmark.json"
START_MARK, END_MARK = "<!-- benchmark:start -->", "<!-- benchmark:end -->"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _title(path: Path) -> str:
    line = next(line for line in _read(path).splitlines() if line.startswith("-- title:"))
    return line.removeprefix("-- title:").strip()


def _link(path: Path) -> str:
    return "../" + path.relative_to(SQL_DIR.parent).as_posix()


def _explain(connection: Connection, sql: str) -> dict:
    query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql.strip().rstrip(';')}"
    return connection.execute(text(query)).scalar_one()[0]


# Walks the plan tree and names how fact_tickets was read (full scan or which index)
def describe_access(plan: dict) -> str:
    accesses, pending = set(), [plan["Plan"]]
    while pending:
        node = pending.pop()
        pending.extend(node.get("Plans", []))
        index = node.get("Index Name", "")
        if node.get("Relation Name") == "fact_tickets" or "fact_tickets" in index:
            accesses.add(f"{node['Node Type']} ({index})" if index else node["Node Type"])
    return ", ".join(sorted(accesses)) or "-"


# Median execution time over several runs, after one warm-up run that fills the cache
def measure(connection: Connection, path: Path) -> tuple[float, str]:
    sql = _read(path)
    _explain(connection, sql)
    plans = [_explain(connection, sql) for _ in range(RUNS)]
    return statistics.median(p["Execution Time"] for p in plans), describe_access(plans[-1])


def _set_indexes(connection: Connection, enabled: bool) -> None:
    if enabled:
        connection.exec_driver_sql(_read(SQL_DIR / "indexes.sql"))
    else:
        for index in INDEXES:
            connection.execute(text(f"DROP INDEX IF EXISTS {index}"))
    connection.execute(text("ANALYZE fact_tickets"))
    connection.commit()


def run_benchmark() -> tuple[dict, dict, dict]:
    with get_engine().connect() as connection:
        _set_indexes(connection, enabled=False)
        without_indexes = {path: measure(connection, path) for path in QUERIES}
        # The indexes stay created at the end, the same state a normal load leaves
        _set_indexes(connection, enabled=True)
        with_indexes = {path: measure(connection, path) for path in QUERIES}
        first_versions = {old: measure(connection, old) for old, _ in REWRITES}
    for path in QUERIES:
        log.info(
            "%s: %.1f ms -> %.1f ms", path.name, without_indexes[path][0], with_indexes[path][0]
        )
    return without_indexes, with_indexes, first_versions


def _ms(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _gain(before: float, after: float) -> str:
    return f"{_ms(before / after)}x" if after else "-"


def results_tables(without_indexes: dict, with_indexes: dict, first_versions: dict) -> str:
    lines = [
        "Índices:",
        "",
        "| Consulta | Sem índice (ms) | Com índice (ms) | Ganho | "
        "Leitura de fact_tickets sem índice | Com índice |",
        "|---|---|---|---|---|---|",
    ]
    for path in QUERIES:
        (before, before_plan), (after, after_plan) = without_indexes[path], with_indexes[path]
        lines.append(
            f"| [{_title(path)}]({_link(path)}) | {_ms(before)} | {_ms(after)} | "
            f"{_gain(before, after)} | {before_plan} | {after_plan} |"
        )
    lines += [
        "",
        "Reescrita, com os índices criados:",
        "",
        "| Consulta | Primeira versão (ms) | Reescrita (ms) | Ganho |",
        "|---|---|---|---|",
    ]
    for old, new in REWRITES:
        before, after = first_versions[old][0], with_indexes[new][0]
        lines.append(
            f"| [{_title(new)}]({_link(new)}) ([primeira versão]({_link(old)})) | "
            f"{_ms(before)} | {_ms(after)} | {_gain(before, after)} |"
        )
    return "\n".join(lines)


# Replaces only the generated block of the report, keeping the text written around it
def write_report(tables: str) -> None:
    report = _read(REPORT_PATH)
    start, end = report.index(START_MARK) + len(START_MARK), report.index(END_MARK)
    REPORT_PATH.write_text(report[:start] + "\n" + tables + "\n" + report[end:], encoding="utf-8")
    log.info("Results written to %s", REPORT_PATH)


# The same numbers as the report, in a shape the dashboard can read
def write_results(without_indexes: dict, with_indexes: dict, first_versions: dict) -> None:
    results = {
        "indexes": [
            {
                "query": _title(path),
                "without_ms": without_indexes[path][0],
                "with_ms": with_indexes[path][0],
                "without_plan": without_indexes[path][1],
                "with_plan": with_indexes[path][1],
            }
            for path in QUERIES
        ],
        "rewrites": [
            {
                "query": _title(new),
                "first_ms": first_versions[old][0],
                "rewritten_ms": with_indexes[new][0],
            }
            for old, new in REWRITES
        ],
    }
    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    measured = run_benchmark()
    write_report(results_tables(*measured))
    write_results(*measured)
