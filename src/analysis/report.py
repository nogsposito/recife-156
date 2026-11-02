import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import Engine, text

from src.analysis.charts import (
    format_number,
    plot_monthly_trend,
    plot_resolution_heatmap,
    plot_volume_by_group,
)
from src.config import DOCS_DIR, SQL_DIR
from src.db.load import get_engine

log = logging.getLogger(__name__)

QUERIES_DIR = SQL_DIR / "analyses"
IMAGES_DIR = DOCS_DIR / "img"
REPORT_PATH = DOCS_DIR / "analises.md"

# Long results are cut in the report; the full output comes from running the SQL file
DEFAULT_ROW_LIMIT = 15
ROW_LIMITS = {"monthly_trend": 36, "resolution_time_by_group": 25}

COLUMN_LABELS = {
    "group_name": "Grupo",
    "service_name": "Serviço",
    "neighborhood_name": "Bairro",
    "tickets": "Chamados",
    "pct_total": "% do total",
    "cumulative_pct": "% acumulado",
    "position": "Posição",
    "month": "Mês",
    "tickets_last_year": "Mesmo mês do ano anterior",
    "yoy_change_pct": "Variação anual (%)",
    "city_rank": "Posição na cidade",
    "rpa": "RPA",
    "rank_in_rpa": "Posição na RPA",
    "pct_resolved": "% atendidos",
    "resolved_tickets": "Atendidos",
    "median_days": "Mediana (dias)",
    "p90_days": "P90 (dias)",
    "pct_within_7_days": "% em até 7 dias",
    "open_tickets": "Em aberto",
    "up_to_30_days": "Até 30 dias",
    "from_31_to_180_days": "31 a 180 dias",
    "over_180_days": "Mais de 180 dias",
    "pct_over_180_days": "% acima de 180 dias",
    "weekday_number": "Nº",
    "weekday": "Dia",
    "avg_tickets_per_day": "Média por dia",
}

MONTH_NAMES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]  # fmt: skip


@dataclass
class Analysis:
    path: Path
    title: str
    question: str
    result: pd.DataFrame


def _header_value(sql: str, key: str) -> str:
    prefix = f"-- {key}:"
    for line in sql.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


# Runs every file in sql/analyses; "03_monthly_trend.sql" is stored as "monthly_trend"
def run_analyses(engine: Engine) -> dict[str, Analysis]:
    analyses = {}
    with engine.connect() as connection:
        for path in sorted(QUERIES_DIR.glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            result = pd.read_sql(text(sql), connection)
            name = path.stem.split("_", 1)[1]
            analyses[name] = Analysis(
                path, _header_value(sql, "title"), _header_value(sql, "question"), result
            )
            log.info("Ran %s (%d rows)", path.name, len(result))
    return analyses


def _pct(value: float) -> str:
    return f"{format_number(value, 1)}%"


def _format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _format_cell(column: str, value) -> str:
    if pd.isna(value):
        return "-"
    if column == "month":
        return pd.Timestamp(value).strftime("%m/%Y")
    if column.startswith("pct") or column.endswith("pct"):
        return format_number(value, 1)
    if isinstance(value, float | np.floating):
        return format_number(value, 0 if float(value).is_integer() else 1)
    if isinstance(value, int | np.integer) and column not in ("rpa", "weekday_number"):
        return format_number(value)
    return str(value)


def to_markdown(df: pd.DataFrame, max_rows: int) -> str:
    shown = df.head(max_rows)
    lines = [
        "| " + " | ".join(COLUMN_LABELS.get(column, column) for column in shown.columns) + " |",
        "|" + "---|" * len(shown.columns),
    ]
    for row in shown.itertuples(index=False):
        pairs = zip(shown.columns, row, strict=True)
        cells = [_format_cell(column, value) for column, value in pairs]
        lines.append("| " + " | ".join(cells) + " |")
    if len(df) > max_rows:
        lines.append(f"\nMostrando {max_rows} de {len(df)} linhas.")
    return "\n".join(lines)


# One-sentence reading of each result, computed from the data so it stays true on reruns
def _insight_volume_by_group(df: pd.DataFrame) -> str:
    top = df.iloc[0]
    return (
        f"{top.group_name} responde por {_pct(top.pct_total)} dos chamados, e os três maiores "
        f"grupos somam {_pct(df.pct_total.head(3).sum())}."
    )


def _insight_service_concentration(df: pd.DataFrame) -> str:
    services_for_80 = int((df.cumulative_pct < 80).sum()) + 1
    return (
        f"Dos {len(df)} serviços com chamados no período, {services_for_80} concentram 80% do "
        f"volume. Detalhes na hipótese H1."
    )


def _insight_monthly_trend(df: pd.DataFrame) -> str:
    months = pd.to_datetime(df.month)
    totals = df.groupby(months.dt.year).tickets.sum()
    peak = df.loc[df.tickets.idxmax()]
    peak_month = pd.Timestamp(peak.month)
    sentences = []
    if len(totals) >= 2:
        last, previous = totals.index[-1], totals.index[-2]
        change = 100 * (totals[last] - totals[previous]) / totals[previous]
        direction = "a mais" if change >= 0 else "a menos"
        sentences.append(
            f"Em {last} foram abertos {format_number(totals[last])} chamados, "
            f"{_pct(abs(change))} {direction} que em {previous}."
        )
    sentences.append(
        f"O mês de maior volume foi {MONTH_NAMES[peak_month.month - 1]} de {peak_month.year} "
        f"({format_number(peak.tickets)} chamados)."
    )
    return " ".join(sentences)


def _insight_neighborhood_ranking(df: pd.DataFrame) -> str:
    top = df.iloc[0]
    worst = df.loc[df.pct_resolved.idxmin()]
    best = df.loc[df.pct_resolved.idxmax()]
    return (
        f"{top.neighborhood_name} (RPA {top.rpa}) lidera com {format_number(top.tickets)} "
        f"chamados. Entre esses bairros, a parcela já atendida vai de {_pct(worst.pct_resolved)} "
        f"({worst.neighborhood_name}) a {_pct(best.pct_resolved)} ({best.neighborhood_name})."
    )


def _insight_resolution_time_by_group(df: pd.DataFrame) -> str:
    slowest, fastest = df.iloc[0], df.iloc[-1]
    return (
        f"{fastest.group_name} tem mediana de {format_number(fastest.median_days)} dias, enquanto "
        f"{slowest.group_name} leva {format_number(slowest.median_days)}. A conta considera só "
        f"chamados já atendidos: em grupos com fila grande, o tempo real tende a ser maior."
    )


def _insight_resolution_time_by_rpa(df: pd.DataFrame) -> str:
    return "Ver hipótese H2 e o mapa de calor na seção de gráficos."


def _insight_backlog_aging(df: pd.DataFrame) -> str:
    total = df.open_tickets.sum()
    old_share = 100 * df.over_180_days.sum() / total
    top = df.iloc[0]
    return (
        f"Nos {len(df)} grupos com maior fila, {format_number(total)} chamados seguiam em aberto "
        f"no fim do recorte, {_pct(old_share)} deles há mais de 180 dias. {top.group_name} "
        f"sozinho tem {format_number(top.open_tickets)}."
    )


def _insight_weekday_profile(df: pd.DataFrame) -> str:
    weekdays_share = 100 * df[df.weekday_number <= 5].tickets.sum() / df.tickets.sum()
    return (
        f"Dias úteis concentram {_pct(weekdays_share)} dos chamados, o que sugere dimensionar "
        f"a equipe de triagem pelo calendário útil."
    )


INSIGHTS: dict[str, Callable[[pd.DataFrame], str]] = {
    "volume_by_group": _insight_volume_by_group,
    "service_concentration": _insight_service_concentration,
    "monthly_trend": _insight_monthly_trend,
    "neighborhood_ranking": _insight_neighborhood_ranking,
    "resolution_time_by_group": _insight_resolution_time_by_group,
    "resolution_time_by_rpa": _insight_resolution_time_by_rpa,
    "backlog_aging": _insight_backlog_aging,
    "weekday_profile": _insight_weekday_profile,
}


def hypothesis_concentration(services: pd.DataFrame) -> str:
    share_top10 = services.cumulative_pct.iloc[min(10, len(services)) - 1]
    first = services.iloc[0]
    verdict = "Confirmada" if share_top10 >= 70 else "Refutada"
    return f"""### H1. Poucos serviços concentram a maior parte da demanda

Hipótese: os 10 serviços mais pedidos somam pelo menos 70% dos chamados.

Por que importa: se a demanda é concentrada, prevenir ou automatizar poucos serviços alivia a \
central de forma desproporcional.

Como foi testada: participação acumulada dos serviços ordenados por volume \
([02_service_concentration.sql](../sql/analyses/02_service_concentration.sql)).

Resultado: {verdict}. Os 10 primeiros, de {len(services)} serviços, somam {_pct(share_top10)} \
dos chamados. Só "{first.service_name}" ({first.group_name}) responde por \
{_pct(first.pct_total)}: é o pedido em que prevenção ou um canal automático teria o maior \
efeito isolado sobre o volume da central.
"""


# A group is "unequal" when its slowest RPA waits more than twice the fastest one and the gap
# is larger than a week, which keeps tiny differences (1 vs 2 days) from counting
def regional_gaps(resolution: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group, data in resolution.groupby("group_name"):
        fastest = data.loc[data.median_days.idxmin()]
        slowest = data.loc[data.median_days.idxmax()]
        ratio = slowest.median_days / max(fastest.median_days, 1)
        gap = slowest.median_days - fastest.median_days
        rows.append(
            {
                "group_name": group,
                "fastest": f"RPA {fastest.rpa} ({format_number(fastest.median_days)} d)",
                "slowest": f"RPA {slowest.rpa} ({format_number(slowest.median_days)} d)",
                "ratio": ratio,
                "unequal": ratio > 2 and gap > 7,
            }
        )
    return pd.DataFrame(rows).sort_values("ratio", ascending=False)


def hypothesis_regional_equity(resolution: pd.DataFrame) -> str:
    gaps = regional_gaps(resolution)
    unequal = gaps[gaps.unequal].group_name.tolist()
    equal = gaps[~gaps.unequal].group_name.tolist()
    if not unequal:
        verdict = "Confirmada para todos os grupos analisados."
    elif not equal:
        verdict = "Refutada para todos os grupos analisados."
    else:
        verdict = f"Refutada para {' e '.join(unequal)}; vale para {' e '.join(equal)}."

    table = ["| Grupo | RPA mais rápida | RPA mais lenta | Lenta / rápida |", "|---|---|---|---|"]
    for row in gaps.itertuples():
        table.append(
            f"| {row.group_name} | {row.fastest} | {row.slowest} | {format_number(row.ratio, 1)}x |"
        )
    table_md = "\n".join(table)

    return f"""### H2. O tempo de atendimento é parecido entre as regiões da cidade

Hipótese: dentro de um mesmo grupo de serviço, a região (RPA) mais lenta não leva mais que o \
dobro do tempo da mais rápida, considerando a mediana de dias até o atendimento.

Por que importa: se a espera depende da região e não só do tipo de serviço, há um problema de \
capacidade ou de contrato regional que a gestão pode atacar diretamente.

Como foi testada: mediana de dias até o atendimento por grupo e RPA, nos quatro maiores grupos \
([06_resolution_time_by_rpa.sql](../sql/analyses/06_resolution_time_by_rpa.sql)). Um grupo \
conta como desigual quando a RPA mais lenta leva mais que o dobro da mais rápida e a diferença \
passa de 7 dias.

{table_md}

Resultado: {verdict}

Limitações: a mediana considera só chamados já atendidos, e a mistura de serviços dentro de um \
grupo pode variar entre regiões. A data de atendimento é a da última mudança de situação \
registrada, que pode refletir a prática de registro de cada equipe, e não só o trabalho em campo.
"""


def _dataset_summary(engine: Engine) -> dict:
    query = """
        SELECT COUNT(*) AS tickets, MIN(opened_on) AS first_day, MAX(opened_on) AS last_day,
               MAX(status_updated_on) AS reference_date
        FROM tickets
    """
    with engine.connect() as connection:
        return dict(connection.execute(text(query)).mappings().one())


def build_report() -> None:
    engine = get_engine()
    analyses = run_analyses(engine)
    summary = _dataset_summary(engine)

    plot_monthly_trend(analyses["monthly_trend"].result, IMAGES_DIR / "monthly_trend.png")
    plot_volume_by_group(analyses["volume_by_group"].result, IMAGES_DIR / "volume_by_group.png")
    plot_resolution_heatmap(
        analyses["resolution_time_by_rpa"].result, IMAGES_DIR / "resolution_by_rpa.png"
    )

    sections = []
    for number, (name, analysis) in enumerate(analyses.items(), start=1):
        limit = ROW_LIMITS.get(name, DEFAULT_ROW_LIMIT)
        insight = INSIGHTS[name](analysis.result) if name in INSIGHTS else ""
        sections.append(
            f"### {number}. {analysis.title}\n\n"
            f"Pergunta: {analysis.question}\n\n"
            f"Consulta: [{analysis.path.name}](../sql/analyses/{analysis.path.name})\n\n"
            f"{to_markdown(analysis.result, limit)}\n\n"
            f"{insight}\n"
        )

    report = f"""# Análises dos chamados do 156

Relatório gerado por `make report` ([src/analysis/report.py](../src/analysis/report.py)) a \
partir das consultas em [sql/analyses](../sql/analyses). Todos os números vêm da execução \
dessas consultas sobre o banco carregado.

Recorte: {format_number(summary["tickets"])} chamados abertos entre \
{_format_date(summary["first_day"])} e {_format_date(summary["last_day"])}, com a situação \
conhecida até {_format_date(summary["reference_date"])}.

## Hipóteses de negócio

{hypothesis_concentration(analyses["service_concentration"].result)}
{hypothesis_regional_equity(analyses["resolution_time_by_rpa"].result)}
## Gráficos

![Chamados abertos por mês](img/monthly_trend.png)

![Chamados por grupo de serviço](img/volume_by_group.png)

![Mediana de dias até o atendimento por região](img/resolution_by_rpa.png)

No mapa de calor a cor segue escala logarítmica, porque os valores vão de 1 dia a vários meses.

## Consultas

{chr(10).join(sections)}"""

    REPORT_PATH.write_text(report, encoding="utf-8")
    log.info("Report written to %s", REPORT_PATH)
