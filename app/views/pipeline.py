import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.data import (
    fmt_int,
    fmt_num,
    load_doc_json,
    load_layer_sizes,
    load_pipeline_runs,
    load_quality_checks,
    load_source_versions,
)
from src.dashboard.style import ACCENT, INK, NEUTRAL, show
from src.dashboard.ui import Stat, Step, callout, flow, header, note, section, stats

CHECK_LABELS = {
    "tickets_not_empty": "A carga tem chamados",
    "required_fields_present": "Campos obrigatórios preenchidos",
    "opened_within_years": "Abertura dentro dos anos carregados",
    "status_updated_after_opening": "Situação atualizada depois da abertura",
    "rpa_between_1_and_6": "RPA entre 1 e 6",
    "coordinates_inside_recife": "Coordenadas dentro do Recife",
    "one_group_per_service": "Cada serviço em um único grupo",
    "known_statuses": "Só situações conhecidas",
    "few_missing_neighborhoods": "Poucos chamados sem bairro",
    "one_weather_row_per_day": "Um registro de chuva por dia",
    "weather_covers_ticket_days": "Chuva para todos os dias com chamado",
    "precipitation_not_negative": "Chuva nunca negativa",
}
SOURCE_LABELS = {"tickets": "Chamados", "weather": "Chuva"}
RUN_STATUS = {"success": "concluída", "failed": "falhou", "running": "em andamento"}

runs = load_pipeline_runs()
successful = runs[runs["status"] == "success"]
if successful.empty:
    st.warning("Nenhuma carga concluída ainda. Rode `make pipeline` e recarregue a página.")
    st.stop()
last = successful.iloc[0]
checks = load_quality_checks(int(last["run_id"]))
blocking = checks[checks["severity"] == "error"]
sizes = load_layer_sizes()
duration = (last["finished_at"] - last["started_at"]).total_seconds()

header(
    "Pipeline de dados",
    f"Cada carga passa por {len(checks)} checagens antes de chegar ao banco",
    "O pipeline baixa os dados abertos e a chuva, guarda o arquivo bruto com versão, limpa, "
    "valida e carrega um esquema estrela no PostgreSQL. Tudo roda do zero com docker compose up, "
    "e uma nova execução só baixa o que mudou no portal.",
)
stats(
    [
        Stat(
            f"{last['finished_at']:%d/%m/%Y}",
            "última carga concluída",
            f"execução nº {last['run_id']}",
        ),
        Stat(f"{duration:.0f} s", "da limpeza à carga no banco"),
        Stat(f"{int(checks['passed'].sum())} de {len(checks)}", "checagens aprovadas"),
        Stat(fmt_int(sizes["fact_tickets"]), "linhas na tabela fato"),
    ]
)

section("Do portal ao painel", "As camadas do pipeline e o que cada uma garante.")
flow(
    [
        Step(
            "FONTES",
            "Ingestão",
            [
                "API CKAN do portal do Recife",
                "API do Open-Meteo",
                "Novas tentativas em falha de rede",
            ],
        ),
        Step(
            "BRONZE",
            "Bruto e versionado",
            ["Parquet por ano, como veio", "Manifesto com versão e hash", "Cópia em MongoDB"],
        ),
        Step(
            "SILVER",
            "Limpo e validado",
            ["Tipos, textos e coordenadas", "Deduplicação entre arquivos", "Portão de qualidade"],
            f"{fmt_int(last['silver_rows'])} chamados",
        ),
        Step(
            "GOLD",
            "Esquema estrela",
            [
                f"Fato com {fmt_int(sizes['fact_tickets'])} chamados",
                f"{sizes['dim_service']} serviços, {sizes['dim_neighborhood']} bairros",
                f"{fmt_int(sizes['dim_date'])} dias com chuva",
            ],
        ),
        Step(
            "OPS",
            "Rastreabilidade",
            ["Cada execução registrada", "Resultado de cada checagem", "Versão de cada fonte lida"],
        ),
    ]
)

left, right = st.columns([3, 2], gap="large")
with left:
    section(
        f"{int(blocking['passed'].sum())} de {len(blocking)} checagens que bloqueiam a carga "
        "passaram",
        "Uma checagem de bloqueio que falha interrompe a carga antes de tocar no banco, e o "
        "painel continua com os dados anteriores. As de aviso só ficam registradas.",
    )
    table = checks.assign(
        check=checks["check_name"].map(CHECK_LABELS).fillna(checks["check_name"]),
    )
    table["check"] = table["check"] + table["severity"].map({"warning": " (aviso)"}).fillna("")
    st.dataframe(
        table[["check", "passed", "details"]],
        hide_index=True,
        height=460,
        column_config={
            "check": st.column_config.TextColumn("Checagem"),
            "passed": st.column_config.CheckboxColumn("Passou", width="small"),
            "details": st.column_config.TextColumn("Resultado"),
        },
    )

with right:
    versions = load_source_versions(int(last["run_id"]))
    section(
        "Cada fonte entra com versão e hash",
        "Se o portal publica uma versão nova com o mesmo conteúdo, o hash é igual e nada é "
        "reprocessado.",
    )
    if versions.empty:
        st.caption("Esta carga é anterior ao registro de versões.")
    else:
        parts = versions["source"].str.split("/", expand=True)
        versions = versions.assign(
            name=parts[0].map(SOURCE_LABELS).fillna(parts[0]) + " " + parts[1],
            hash=versions["sha256"].str[:12].fillna("-"),
            version=pd.to_datetime(versions["version"], format="ISO8601").dt.strftime("%d/%m/%Y"),
        )
        st.dataframe(
            versions[["name", "rows", "version", "hash"]],
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("Fonte"),
                "rows": st.column_config.NumberColumn("Linhas", format="localized"),
                "version": st.column_config.TextColumn("Versão no portal"),
                "hash": st.column_config.TextColumn("SHA-256"),
            },
        )
    section("Últimas execuções")
    history = runs.assign(
        seconds=(runs["finished_at"] - runs["started_at"]).dt.total_seconds().round(),
        status=runs["status"].map(RUN_STATUS).fillna(runs["status"]),
        changed_inputs=runs["changed_inputs"].replace({"none": "nada", "not checked": "-"}),
    )
    st.dataframe(
        history[["run_id", "started_at", "status", "changed_inputs", "seconds"]].head(8),
        hide_index=True,
        column_config={
            "run_id": st.column_config.NumberColumn("Nº", format="%d"),
            "started_at": st.column_config.DatetimeColumn("Início", format="DD/MM/YY HH:mm"),
            "status": st.column_config.TextColumn("Situação"),
            "changed_inputs": st.column_config.TextColumn("O que mudou"),
            "seconds": st.column_config.NumberColumn("Duração (s)", format="%d"),
        },
    )

benchmark = load_doc_json("benchmark.json")
if benchmark is not None:
    indexes = benchmark["indexes"]
    best = max(indexes, key=lambda row: row["without_ms"] / row["with_ms"])
    rewrite = benchmark["rewrites"][0]
    section(
        f"O índice certo deixa a consulta mais usada {best['without_ms'] / best['with_ms']:.0f} "
        "vezes mais rápida",
        "Tempo de execução (mediana de 15 rodadas de EXPLAIN ANALYZE) sem e com os índices. "
        "Escala logarítmica: cada marca do eixo é dez vezes a anterior.",
    )
    fig = go.Figure()
    for row in indexes:
        fig.add_shape(
            type="line",
            x0=row["with_ms"],
            x1=row["without_ms"],
            y0=row["query"],
            y1=row["query"],
            line={"color": NEUTRAL, "width": 2},
        )
    queries = [row["query"] for row in indexes]
    fig.add_scatter(
        x=[row["without_ms"] for row in indexes],
        y=queries,
        mode="markers",
        marker={"color": NEUTRAL, "size": 11},
        name="Sem índice",
        customdata=[row["without_plan"] for row in indexes],
        hovertemplate="Sem índice: %{x:.1f} ms<br>%{customdata}<extra></extra>",
    )
    fig.add_scatter(
        x=[row["with_ms"] for row in indexes],
        y=queries,
        mode="markers+text",
        marker={"color": ACCENT, "size": 11},
        name="Com índice",
        text=[f"{row['without_ms'] / row['with_ms']:.0f}x" for row in indexes],
        textposition="middle left",
        textfont={"color": INK},
        customdata=[row["with_plan"] for row in indexes],
        hovertemplate="Com índice: %{x:.1f} ms<br>%{customdata}<extra></extra>",
    )
    fig.update_xaxes(
        type="log",
        title="Milissegundos (escala log)",
        showgrid=True,
        range=[-1.6, 3.3],
        tickvals=[0.1, 1, 10, 100, 1000],
        ticktext=["0,1", "1", "10", "100", "1.000"],
    )
    fig.update_yaxes(showline=False, gridcolor="rgba(0,0,0,0)", autorange="reversed")
    show(fig, height=260)
    callout(
        f"Na consulta de chuva por dia, índice não ajuda: ela precisa ler todos os chamados. O que "
        f"funcionou foi reescrever, agregando antes de juntar com a chuva: de "
        f"{fmt_num(rewrite['first_ms'])} ms para {fmt_num(rewrite['rewritten_ms'])} ms."
    )
    note(
        "Tempos de uma máquina local com o banco no Docker; o valor absoluto muda, a comparação "
        "não. Planos e custos em docs/sql_optimization.md."
    )
