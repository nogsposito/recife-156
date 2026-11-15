import json

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.config import PROJECT_ROOT
from src.dashboard.data import fmt_int, fmt_num, fmt_pct
from src.dashboard.labels import rpa_label

# Official boundaries from the Recife open data portal ("Bairros do Recife"), simplified to ~6 m
BOUNDARIES_PATH = PROJECT_ROOT / "app" / "assets" / "recife_bairros.geojson"
# Three neighborhoods are spelled differently in the boundaries file and in the 156 data
ALIASES = {
    "ALTO DO MANDU": "ALTO DO MANDU SITIO GRANDE",
    "COHAB": "COHAB IBURA DE CIMA",
    "SITIO DOS PINTOS": "SITIO DOS PINTOS SAO BRAS",
}
# Groups that rise after heavy rain (notebook 03)
RAIN_GROUPS = {"Drenagem", "Arborização"}
# Dark to bright blue: the brighter the neighborhood, the more open tickets
STEPS = ["#1f3b63", "#1f5a96", "#2f7cc7", "#4f9de6", "#86c0f5", "#c4e2ff"]
RECIFE = [-8.045, -34.925]
TIP_STYLE = (
    "background-color:#131824;color:#e9edf3;border:1px solid #2a3242;border-radius:8px;"
    "font-family:Outfit,system-ui,sans-serif;font-size:13px;padding:8px 10px;"
)
# OpenStreetMap tiles need no key; the filter turns them dark only in the tile layer, so the
# neighborhood colours on top stay as they are. Leaflet's popup is white by default too.
POPUP_CSS = """<style>
.leaflet-tile-pane {
  filter: invert(1) hue-rotate(180deg) brightness(.92) contrast(.88) saturate(.55);
}
.leaflet-container { background:#0a0d14; }
.leaflet-popup-content-wrapper, .leaflet-popup-tip { background:#131824; color:#e9edf3;
  border:1px solid #2a3242; box-shadow:0 8px 24px rgba(0,0,0,.4); }
.leaflet-popup-content { font-family:Outfit,system-ui,sans-serif; font-size:13px; line-height:1.5;
  margin:12px 14px; }
.leaflet-popup-content table th { display:none; }
.leaflet-popup-content td:first-child { font-weight:600; font-size:15px; }
.leaflet-container a.leaflet-popup-close-button { color:#8891a1; }
</style>"""


@st.cache_data
def load_boundaries() -> dict:
    data = json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))
    for feature in data["features"]:
        props = feature["properties"]
        props["name"] = ALIASES.get(props["name"], props["name"])
        props["rpa"] = int(props["rpa"])
    return data


def neighborhood_stats(tickets: pd.DataFrame, reference: pd.Timestamp, by: str) -> pd.DataFrame:
    open_tickets = tickets[tickets["is_open"]]
    resolved = tickets[~tickets["is_open"]]
    # Waiting time relative to the same service in the whole city, so a neighborhood is not
    # called slow only because it asks for slow services
    service_median = resolved.groupby("service_name")["days_to_last_update"].median().clip(lower=1)
    relative = resolved["days_to_last_update"] / resolved["service_name"].map(service_median)
    old = (reference - open_tickets["opened_on"]).dt.days > 180

    stats = pd.DataFrame(
        {
            "open_tickets": open_tickets.groupby("neighborhood_name").size(),
            "over_180": old.groupby(open_tickets["neighborhood_name"]).mean(),
            "relative_wait": relative.groupby(resolved["neighborhood_name"]).median(),
        }
    )
    top = (
        open_tickets.groupby(["neighborhood_name", by], observed=True)
        .size()
        .rename("n")
        .reset_index()
        .sort_values("n", ascending=False)
        .drop_duplicates("neighborhood_name")
        .set_index("neighborhood_name")
    )
    stats["top"] = top[by].astype(str)
    stats["top_share"] = top["n"] / stats["open_tickets"]
    stats["open_tickets"] = stats["open_tickets"].fillna(0).astype(int)
    return stats


# A short reading of one neighborhood, built from its numbers (no language model involved)
def describe(row: pd.Series, city_over_180: float) -> str:
    if not row.get("open_tickets"):
        return "Nenhum chamado em aberto com esse filtro."
    parts = [
        f"{row['top']} puxa a fila: {fmt_pct(100 * row['top_share'], 0)} dos "
        f"{fmt_int(row['open_tickets'])} pedidos em aberto."
    ]
    over, gap = row["over_180"], row["over_180"] - city_over_180
    city = fmt_pct(100 * city_over_180, 0)
    if gap > 0.1:
        parts.append(
            f"{fmt_pct(100 * over, 0)} esperam há mais de seis meses, acima da cidade ({city})."
        )
    elif gap < -0.1:
        parts.append(
            f"{fmt_pct(100 * over, 0)} esperam há mais de seis meses, abaixo da cidade ({city})."
        )
    else:
        parts.append(
            f"{fmt_pct(100 * over, 0)} esperam há mais de seis meses, perto da cidade ({city})."
        )
    wait = row.get("relative_wait")
    if pd.notna(wait):
        if wait >= 1.3:
            parts.append(
                f"Nos mesmos serviços, o atendimento aqui leva {fmt_num(wait)} vezes o tempo da "
                "cidade."
            )
        elif wait <= 0.77:
            parts.append(
                f"Nos mesmos serviços, o atendimento aqui leva {fmt_pct(100 * wait, 0)} do tempo "
                "da cidade."
            )
        else:
            parts.append("Nos mesmos serviços, o tempo de atendimento é parecido com o da cidade.")
    if row["top"] in RAIN_GROUPS:
        parts.append(
            f"{row['top']} sobe depois de chuva forte, então a fila daqui tende a crescer depois "
            "de temporais."
        )
    return " ".join(parts)


# Map tiles come from OpenStreetMap; the neighborhoods are a light layer on top, there to
# answer the pointer. Returns the neighborhood clicked last, or `default`.
def neighborhood_map(
    boundaries: dict, stats: pd.DataFrame, city_over_180: float, default: str, height: int = 520
) -> str:
    previous = st.session_state.get("bairros_map") or {}
    clicked = (previous.get("last_active_drawing") or {}).get("properties", {}).get("name")
    selected = clicked or default

    ranks = stats["open_tickets"].rank(pct=True)
    features = []
    for feature in boundaries["features"]:
        props = dict(feature["properties"])
        name = props["name"]
        known = name in stats.index
        step = min(int(ranks[name] * len(STEPS)), len(STEPS) - 1) if known else 0
        props.update(
            region=rpa_label(props["rpa"]),
            queue=f"{fmt_int(stats.loc[name, 'open_tickets']) if known else 0} chamados em aberto",
            summary=describe(stats.loc[name], city_over_180)
            if known
            else "Sem chamados em aberto.",
            fill=STEPS[step],
            selected=name == selected,
        )
        features.append({**feature, "properties": props})

    world = folium.Map(location=RECIFE, zoom_start=12, tiles="OpenStreetMap", prefer_canvas=True)
    world.get_root().header.add_child(folium.Element(POPUP_CSS))
    folium.GeoJson(
        {"type": "FeatureCollection", "features": features},
        name="bairros",
        style_function=lambda f: {
            "fillColor": f["properties"]["fill"],
            "fillOpacity": 0.34,
            "color": "#e9edf3" if f["properties"]["selected"] else "#5ab9fc",
            "weight": 2.5 if f["properties"]["selected"] else 0.7,
            "opacity": 0.9 if f["properties"]["selected"] else 0.45,
        },
        highlight_function=lambda f: {"weight": 2.5, "color": "#e9edf3", "fillOpacity": 0.6},
        tooltip=folium.GeoJsonTooltip(
            fields=["label", "region", "queue"], labels=False, sticky=True, style=TIP_STYLE
        ),
        popup=folium.GeoJsonPopup(fields=["label", "summary"], labels=False, max_width=300),
    ).add_to(world)
    st_folium(
        world,
        height=height,
        use_container_width=True,
        returned_objects=["last_active_drawing"],
        key="bairros_map",
    )
    return selected
