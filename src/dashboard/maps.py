import pandas as pd
import pydeck as pdk
import streamlit as st

# Dark to bright blue: the brighter and taller the column, the more open tickets in the area
COLOR_RANGE = [
    [23, 58, 99],
    [31, 90, 150],
    [47, 124, 199],
    [79, 157, 230],
    [134, 192, 245],
    [196, 226, 255],
]
RECIFE = pdk.ViewState(latitude=-8.06, longitude=-34.925, zoom=11.2, pitch=48, bearing=-18)


def queue_map(points: pd.DataFrame, height: int = 460) -> None:
    layer = pdk.Layer(
        "HexagonLayer",
        data=points[["longitude", "latitude"]],
        get_position=["longitude", "latitude"],
        radius=260,
        elevation_scale=6,
        elevation_range=[0, 900],
        extruded=True,
        coverage=0.88,
        color_range=COLOR_RANGE,
        pickable=True,
        auto_highlight=True,
    )
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=RECIFE,
        map_provider="carto",
        map_style=pdk.map_styles.DARK,
        tooltip={
            "html": "<b>{elevationValue}</b> chamados em aberto",
            "style": {"backgroundColor": "#131824", "color": "#e9edf3", "fontFamily": "Outfit"},
        },
    )
    st.pydeck_chart(deck, height=height)
