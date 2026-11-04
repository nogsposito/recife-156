import unicodedata

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.data import fmt_int, fmt_pct, load_doc_json, load_service_mapping
from src.dashboard.labels import sentence_label
from src.dashboard.style import ACCENT, INK, NEUTRAL, show
from src.dashboard.ui import Stat, callout, header, note, section, stats

NEAREST = "Embeddings: serviço atual mais parecido"
SHORT_NAMES = {
    "Caracteres (TF-IDF) + regressão logística": "N-gramas de caracteres + regressão logística",
    "Embeddings (transformer) + regressão logística": "Embeddings + regressão logística",
    NEAREST: "Embeddings: serviço atual mais parecido",
}

mapping = load_service_mapping()
results = load_doc_json("nlp_results.json")
total = mapping["tickets"].sum()
confident = mapping[mapping["similarity"] >= 0.9]
confident_share = 100 * confident["tickets"].sum() / total
group_hits = mapping["suggested_group"] == mapping["group"]

header(
    "Histórico de 2012 a 2023",
    "Doze anos de chamados antigos ligados ao catálogo de serviços atual",
    "Os arquivos de 2012 a 2023 usam outro catálogo e perderam as letras acentuadas na "
    'exportação: "MANUTENO EM LMPADA APAGADA". Para estender as análises de 2 para 14 anos, '
    "três métodos foram comparados para ligar cada descrição antiga a um grupo de hoje, "
    "aprendendo só com as descrições de 2024 e 2025.",
)
stats(
    [
        Stat(fmt_int(len(mapping)), "descrições antigas sem equivalente exato hoje"),
        Stat(fmt_int(total), "chamados de 2012 a 2023 com essas descrições"),
        Stat(
            fmt_pct(100 * mapping.loc[group_hits, "tickets"].sum() / total, 0),
            "dos chamados com o grupo certo",
            "pela sugestão do serviço mais parecido",
        ),
        Stat(fmt_pct(confident_share, 0), "dos chamados com sugestão de alta confiança"),
    ]
)

if results is not None:
    original = results["original"][NEAREST]["ticket_accuracy"]
    repaired = results["com reparo"][NEAREST]["ticket_accuracy"]
    section(
        "Reparar as palavras quebradas leva a busca por similaridade de "
        f"{fmt_pct(100 * original, 0)} para {fmt_pct(100 * repaired, 0)} de acerto",
        "Parte dos chamados antigos posta no grupo certo, por método, com o texto como veio no "
        'arquivo e depois de restaurar as palavras que perderam letras ("LMPADA" vira '
        '"LAMPADA" quando a palavra completa existe no catálogo atual).',
    )
    fig = go.Figure()
    methods = list(SHORT_NAMES)
    for variant, name, color in [
        ("original", "Texto original", NEUTRAL),
        ("com reparo", "Com reparo", ACCENT),
    ]:
        values = [results[variant][method]["ticket_accuracy"] for method in methods]
        fig.add_bar(
            y=[SHORT_NAMES[method] for method in methods],
            x=values,
            orientation="h",
            name=name,
            marker_color=color,
            text=[fmt_pct(100 * value, 0) for value in values],
            textposition="outside",
            textfont={"color": INK},
            cliponaxis=False,
            hovertemplate="%{y}: %{x:.1%}<extra>" + name + "</extra>",
        )
    fig.update_xaxes(visible=False, range=[0, 1.12])
    fig.update_yaxes(autorange="reversed", showline=False, gridcolor="rgba(0,0,0,0)")
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    show(fig, height=280)
    ngrams = results["original"]["Caracteres (TF-IDF) + regressão logística"]["ticket_accuracy"]
    callout(
        f"O classificador de n-gramas acerta o grupo de {fmt_pct(100 * ngrams, 0)} dos chamados "
        "antigos mesmo sem reparo, "
        "porque pedaços de palavra sobrevivem à perda de letras. A busca por embeddings faz mais: "
        "sugere o serviço equivalente, e com o texto reparado passa a acertar o grupo quase "
        "tanto quanto o classificador."
    )

left, right = st.columns([3, 2], gap="large")
with left:
    thresholds = np.round(np.arange(0.5, 1.001, 0.01), 2)
    coverage = [
        100 * mapping.loc[mapping["similarity"] >= t, "tickets"].sum() / total for t in thresholds
    ]
    hits_confident = (
        100
        * confident.loc[confident["suggested_group"] == confident["group"], "tickets"].sum()
        / max(confident["tickets"].sum(), 1)
    )
    section(
        f"{fmt_pct(confident_share, 0)} do histórico pode entrar sem revisão manual",
        "Parte dos chamados antigos cuja sugestão tem pelo menos a similaridade do eixo "
        f"horizontal. A partir de 0,9, o grupo sugerido acertou {fmt_pct(hits_confident, 0)} dos "
        "chamados; abaixo disso, a revisão manual de poucas descrições resolve o resto.",
    )
    fig = go.Figure(
        go.Scatter(
            x=thresholds,
            y=coverage,
            mode="lines",
            line={"color": ACCENT, "width": 2, "shape": "hv"},
            hovertemplate="Similaridade ≥ %{x:.2f}: %{y:.0f}% dos chamados<extra></extra>",
        )
    )
    fig.add_vline(x=0.9, line_color=NEUTRAL, line_width=1)
    fig.add_annotation(
        x=0.9,
        y=confident_share,
        text=f"0,9: {fmt_pct(confident_share, 0)}",
        showarrow=False,
        xanchor="right",
        yanchor="bottom",
        xshift=-6,
        font={"color": INK},
    )
    fig.update_xaxes(title="Similaridade mínima da sugestão", tickformat=".1f")
    fig.update_yaxes(title="Chamados antigos (%)", range=[0, 105])
    show(fig, height=300)

with right:
    repaired = mapping[mapping["service"] != mapping["service_repaired"]].head(8)
    section(
        "Como o reparo funciona",
        "Palavras com letras faltando são trocadas pela palavra do catálogo atual que as contém "
        "na mesma ordem. Exemplos com mais chamados:",
    )
    st.dataframe(
        repaired[["service", "service_repaired"]],
        hide_index=True,
        height=300,
        column_config={
            "service": st.column_config.TextColumn("No arquivo antigo"),
            "service_repaired": st.column_config.TextColumn("Depois do reparo"),
        },
    )

section(
    "O de-para completo",
    "Cada descrição antiga, o serviço atual mais parecido e a similaridade entre os dois. É o "
    "ponto de partida para revisar à mão as poucas descrições com similaridade baixa.",
)
search = st.text_input("Buscar descrição", placeholder="Ex.: poda, lâmpada, galeria")
table = mapping.assign(
    suggested=mapping["suggested_service"].map(sentence_label),
    group_label=mapping["group"].map(sentence_label),
    years=mapping["first_year"].astype(str) + " a " + mapping["last_year"].astype(str),
)
if search:
    query = unicodedata.normalize("NFKD", search.upper()).encode("ascii", "ignore").decode()
    table = table[
        table["service_repaired"].str.contains(query, regex=False)
        | table["suggested_service"].str.contains(query, regex=False)
    ]
st.dataframe(
    table[["service_repaired", "suggested", "similarity", "tickets", "group_label", "years"]],
    hide_index=True,
    column_config={
        "service_repaired": st.column_config.TextColumn("Descrição antiga"),
        "group_label": st.column_config.TextColumn("Grupo"),
        "tickets": st.column_config.NumberColumn("Chamados", format="localized"),
        "years": st.column_config.TextColumn("Anos"),
        "suggested": st.column_config.TextColumn("Serviço atual sugerido"),
        "similarity": st.column_config.ProgressColumn(
            "Similaridade", format="%.2f", min_value=0, max_value=1
        ),
    },
)
note(
    "Embeddings: paraphrase-multilingual-MiniLM-L12-v2 (sentence-transformers), similaridade de "
    "cosseno. N-gramas: TF-IDF de 2 a 4 caracteres. Raciocínio, matriz de confusão e erros no "
    "notebook 05."
)
