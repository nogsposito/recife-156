from dataclasses import dataclass
from html import escape

import streamlit as st

from src.dashboard.style import ACCENT, INK, INK_2, MUTED

CSS = f"""
[data-testid="stMainBlockContainer"] {{ max-width: 1180px; padding-top: 2.2rem; }}
h1, h2, h3 {{ letter-spacing: -0.015em; color: {INK}; }}
[data-testid="stSidebarNav"] span {{ font-size: 0.92rem; }}

.r-kicker {{
    color: {ACCENT}; font-size: 0.78rem; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase; margin: 0 0 0.35rem;
}}
.r-title {{
    font-size: 2.05rem; font-weight: 700; line-height: 1.15; color: {INK};
    letter-spacing: -0.02em; margin: 0 0 0.6rem; max-width: 44ch;
}}
.r-lede {{ font-size: 1.04rem; line-height: 1.55; color: {INK_2}; max-width: 72ch; margin: 0; }}

.r-section {{ margin: 1.6rem 0 0.2rem; }}
.r-section h3 {{ font-size: 1.18rem; font-weight: 600; margin: 0 0 0.25rem; padding: 0; }}
.r-section p {{ color: {INK_2}; font-size: 0.93rem; line-height: 1.5; margin: 0; max-width: 80ch; }}

.r-stats {{
    display: grid; gap: 0.75rem; margin: 1.3rem 0 0.4rem;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
}}
.r-stat {{
    background: #ffffff; border: 1px solid #e6e4df; border-radius: 10px;
    padding: 0.85rem 1rem 0.9rem;
}}
.r-stat-value {{ font-size: 1.7rem; font-weight: 650; color: {INK}; line-height: 1.15; }}
.r-stat-label {{ font-size: 0.86rem; color: {INK_2}; margin-top: 0.2rem; line-height: 1.35; }}
.r-stat-note {{ font-size: 0.78rem; color: {MUTED}; margin-top: 0.35rem; line-height: 1.35; }}

.r-callout {{
    border-left: 3px solid {ACCENT}; background: #f1f6fd; border-radius: 0 8px 8px 0;
    padding: 0.75rem 1rem; color: {INK}; font-size: 0.95rem; line-height: 1.5; margin: 0.8rem 0;
}}
.r-note {{ color: {MUTED}; font-size: 0.8rem; line-height: 1.45; margin: 0.2rem 0 0.6rem; }}

.r-flow {{
    display: grid; gap: 0.5rem; margin: 0.9rem 0 0.4rem;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
}}
.r-step {{
    background: #ffffff; border: 1px solid #e6e4df; border-radius: 10px;
    padding: 0.8rem 0.95rem; position: relative;
}}
.r-step-tag {{ font-size: 0.72rem; font-weight: 600; color: {ACCENT}; letter-spacing: 0.06em; }}
.r-step-name {{ font-size: 1rem; font-weight: 600; color: {INK}; margin: 0.15rem 0 0.35rem; }}
.r-step ul {{
    margin: 0; padding-left: 1rem; color: {INK_2}; font-size: 0.84rem; line-height: 1.45;
}}
.r-step-figure {{ font-size: 0.84rem; color: {INK}; font-weight: 600; margin-top: 0.45rem; }}

"""


@dataclass
class Stat:
    value: str
    label: str
    note: str = ""


@dataclass
class Step:
    tag: str
    name: str
    items: list[str]
    figure: str = ""


def apply_theme() -> None:
    st.html(f"<style>{CSS}</style>")


def header(kicker: str, title: str, lede: str = "") -> None:
    lede_html = f'<p class="r-lede">{escape(lede)}</p>' if lede else ""
    st.html(
        f'<p class="r-kicker">{escape(kicker)}</p><h1 class="r-title">{escape(title)}</h1>'
        f"{lede_html}"
    )


# Section titles state the takeaway; the note says how to read the chart below it
def section(title: str, note: str = "") -> None:
    note_html = f"<p>{escape(note)}</p>" if note else ""
    st.html(f'<div class="r-section"><h3>{escape(title)}</h3>{note_html}</div>')


def stats(items: list[Stat]) -> None:
    cards = "".join(
        f'<div class="r-stat"><div class="r-stat-value">{escape(item.value)}</div>'
        f'<div class="r-stat-label">{escape(item.label)}</div>'
        + (f'<div class="r-stat-note">{escape(item.note)}</div>' if item.note else "")
        + "</div>"
        for item in items
    )
    st.html(f'<div class="r-stats">{cards}</div>')


def callout(text: str) -> None:
    st.html(f'<div class="r-callout">{escape(text)}</div>')


def note(text: str) -> None:
    st.html(f'<p class="r-note">{escape(text)}</p>')


def flow(steps: list[Step]) -> None:
    cards = "".join(
        f'<div class="r-step"><div class="r-step-tag">{escape(step.tag)}</div>'
        f'<div class="r-step-name">{escape(step.name)}</div>'
        "<ul>"
        + "".join(f"<li>{escape(item)}</li>" for item in step.items)
        + "</ul>"
        + (f'<div class="r-step-figure">{escape(step.figure)}</div>' if step.figure else "")
        + "</div>"
        for step in steps
    )
    st.html(f'<div class="r-flow">{cards}</div>')
