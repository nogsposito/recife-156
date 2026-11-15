import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from html import escape

import streamlit as st

from src.dashboard.style import BACKGROUND, CREAM, LINE_STRONG, MUTED, RED, SAGE, SURFACE, TAN

LINE = "#1d2b29"

CSS = f"""
:root {{
    --r-ease: cubic-bezier(.2, .8, .2, 1);
    --r-ease-enter: cubic-bezier(.22, 1, .36, 1);
}}
[data-testid="stAppViewContainer"] {{
    background:
        radial-gradient(900px 420px at 82% -10%, rgba(190, 165, 125, .10), transparent 65%),
        radial-gradient(700px 380px at 5% 0%, rgba(164, 186, 183, .07), transparent 60%),
        {BACKGROUND};
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{
    max-width: 1180px; padding-top: 3.2rem; padding-bottom: 6.5rem;
}}
h1, h2, h3 {{ letter-spacing: -0.02em; color: {CREAM}; }}
[data-testid="stSidebarNav"] span {{ font-size: 0.93rem; }}
[data-testid="stCaptionContainer"] {{ color: {MUTED}; }}

/* Page header: reads like the title of a tab, with its purpose in one line */
.r-head {{
    display: flex; gap: 1.1rem; align-items: flex-start;
    padding-bottom: 1.5rem; margin-bottom: 1.7rem; border-bottom: 1px solid {LINE};
}}
.r-head-icon {{
    flex: none; width: 3.2rem; height: 3.2rem; margin-top: .3rem; border-radius: 12px;
    display: grid; place-items: center; color: {BACKGROUND}; background: {TAN};
    font-family: "Material Symbols Rounded"; font-size: 1.75rem; line-height: 1;
    font-feature-settings: "liga"; animation: r-up .5s var(--r-ease-enter) both;
}}
.r-title {{
    font-size: clamp(2.3rem, 1.5rem + 2.2vw, 3.3rem); font-weight: 500; line-height: 1.05;
    color: {CREAM}; letter-spacing: -0.04em; margin: 0; padding: 0;
}}
.r-w {{ display: inline-block; overflow: hidden; vertical-align: bottom; padding-bottom: .08em; }}
.r-w > span {{
    display: inline-block; animation: r-rise .7s var(--r-ease-enter) both;
    animation-delay: calc(var(--i) * 40ms);
}}
.r-purpose {{
    color: {SAGE}; font-size: 1.08rem; line-height: 1.55; margin: .55rem 0 0; max-width: 64ch;
    animation: r-up .5s var(--r-ease-enter) .2s both;
}}

/* A sentence set large, with its numbers in the accent colour */
.r-statement {{
    font-size: clamp(1.3rem, 1rem + 1vw, 1.8rem); line-height: 1.45; font-weight: 400;
    color: {CREAM}; letter-spacing: -0.015em; max-width: 46ch; margin: 0 0 2rem;
    animation: r-up .55s var(--r-ease-enter) .3s both;
}}
.r-hl {{ color: {TAN}; font-weight: 500; white-space: nowrap; }}

/* Key figures in a row, divided by hairlines, with no boxes around them */
.r-facts {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    margin: 0 0 2rem; row-gap: 1.1rem;
}}
.r-fact {{
    padding: .1rem 1.4rem; border-left: 1px solid {LINE_STRONG};
    animation: r-up .5s var(--r-ease-enter) both; animation-delay: calc(.3s + var(--i) * 60ms);
}}
.r-fact:first-child {{ padding-left: 0; border-left: 0; }}
/* A short colour bar over each number, cycling through the palette */
.r-fact::before {{
    content: ""; display: block; width: 2.4rem; height: 4px; border-radius: 2px;
    margin-bottom: .75rem; background: {TAN};
}}
.r-fact:nth-child(3n+2)::before {{ background: {SAGE}; }}
.r-fact:nth-child(3n)::before {{ background: {CREAM}; }}
.r-fact-value {{
    font-size: 2.1rem; font-weight: 500; color: {CREAM}; line-height: 1.1;
    letter-spacing: -0.03em;
}}
.r-fact-label {{ font-size: 0.9rem; color: {SAGE}; margin-top: 0.3rem; line-height: 1.4; }}
.r-fact-note {{
    font-size: 0.76rem; color: {MUTED}; margin-top: 0.35rem; line-height: 1.4;
    font-family: "DM Mono", ui-monospace, monospace;
}}
@media (max-width: 760px) {{
    .r-facts {{ grid-template-columns: 1fr 1fr; }}
    .r-fact:nth-child(odd) {{ padding-left: 0; border-left: 0; }}
}}

/* Numbers count up once, from zero to the value, without script */
/* The syntax string starts with an escaped angle bracket: the sanitizer drops a raw one */
@property --c {{ syntax: '\\3c integer>'; inherits: false; initial-value: 0; }}
@counter-style r-pad3 {{ system: extends decimal; pad: 3 "0"; }}
.r-c {{
    counter-reset: c var(--c);
    animation: r-count 1.1s var(--r-ease-enter) .4s both;
}}
.r-c::after {{ content: counter(c); }}
.r-c3::after {{ content: counter(c, r-pad3); }}

/* Group headings split a long page into parts; section titles state a chart's takeaway */
.r-group {{ margin: 2.8rem 0 1rem; }}
.r-group h2 {{ font-size: 1.55rem; font-weight: 500; margin: 0; padding: 0; }}
.r-group p {{ color: {SAGE}; font-size: 0.97rem; margin: .3rem 0 0; max-width: 72ch; }}
.r-section {{ margin: 0 0 0.6rem; }}
.r-section h3 {{
    font-size: 1.18rem; font-weight: 500; line-height: 1.35; margin: 0 0 0.3rem; padding: 0;
}}
.r-section p {{
    color: {SAGE}; font-size: 0.92rem; line-height: 1.55; margin: 0; max-width: 78ch;
}}

/* Panels: one bordered box per chart, so each title sits with its own chart and controls.
   Panels side by side stretch to the tallest one; a panel with a fixed height keeps it. */
[class*="st-key-panel-"], [class*="st-key-pfixed-"] {{
    background: {SURFACE}; border: 1px solid rgba(164, 186, 183, .16) !important;
    border-top: 3px solid rgba(190, 165, 125, .75) !important; border-radius: 14px;
    padding: 1.15rem 1.3rem 1rem !important;
}}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-panel-"]) {{
    align-items: stretch;
}}
[data-testid="stColumn"]:has([class*="st-key-panel-"]) > [data-testid="stVerticalBlock"],
[data-testid="stColumn"] [data-testid="stLayoutWrapper"]:has(> [class*="st-key-panel-"]),
[data-testid="stColumn"] [class*="st-key-panel-"] {{
    height: 100%;
}}
/* A link at the foot of a panel stays at the foot when the panels beside it are taller */
[class*="st-key-panel-"] > [data-testid="stElementContainer"]:has([data-testid="stPageLink"]) {{
    margin-top: auto;
}}
[class*="st-key-panel-"] [data-testid="stMarkdownContainer"] p,
[class*="st-key-pfixed-"] [data-testid="stMarkdownContainer"] p {{
    color: {SAGE}; font-size: .95rem; line-height: 1.55;
}}
[class*="st-key-panel-"] [data-testid="stMarkdownContainer"] strong {{
    color: {CREAM}; font-weight: 500; font-size: 1.05rem;
}}
.r-panel-place {{ color: {MUTED}; font-size: .86rem; margin: 0; }}
.r-panel-name {{
    font-size: 1.6rem; font-weight: 500; letter-spacing: -0.03em; color: {CREAM};
    margin: .1rem 0 .9rem;
}}
[class*="st-key-pfixed-"] .r-facts {{
    margin-bottom: 1rem; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
}}
[class*="st-key-pfixed-"] .r-fact-value {{ font-size: 1.7rem; }}

.r-terms {{
    display: grid; gap: 0.8rem; margin: 0.9rem 0 0.2rem; padding: 0;
    grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
}}
.r-term {{ border-top: 1px solid {LINE_STRONG}; padding-top: 0.6rem; margin: 0; }}
.r-term-name {{
    font-family: "DM Mono", ui-monospace, monospace; font-size: 0.74rem; color: {TAN};
    letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 0.25rem;
}}
.r-term-text {{ margin: 0; color: {SAGE}; font-size: 0.88rem; line-height: 1.5; }}

.r-callout {{
    background: {TAN}; border-radius: 12px; padding: 0.9rem 1.15rem; color: {BACKGROUND};
    font-weight: 500;
    font-size: 0.96rem; line-height: 1.55; margin: 0.9rem 0;
}}
.r-note {{ color: {MUTED}; font-size: 0.8rem; line-height: 1.5; margin: 0.4rem 0 0.2rem; }}

/* Pipeline: stages joined by arrows; a pulse runs along each arrow, stage after stage */
.r-pipe {{
    display: grid; align-items: stretch; margin: .6rem 0 .4rem;
    grid-template-columns: 1.25fr 60px 1fr 60px 1fr 60px 1fr 60px 1.25fr;
}}
.r-pipe-node {{
    background: {SURFACE}; border: 1px solid {LINE}; border-radius: 12px;
    padding: .85rem .9rem;
    animation: r-node 3s var(--r-ease) 3 both; animation-delay: calc(1s + var(--i) * .75s);
}}
.r-pipe-tag {{
    font-family: "DM Mono", ui-monospace, monospace; font-size: .7rem; color: {TAN};
    letter-spacing: .08em; text-transform: uppercase;
}}
.r-pipe-name {{ font-size: 1rem; font-weight: 500; color: {CREAM}; margin: .2rem 0 .35rem; }}
.r-pipe-text {{ color: {SAGE}; font-size: .8rem; line-height: 1.45; }}
.r-pipe-figure {{
    color: {CREAM}; font-size: .8rem; margin-top: .5rem;
    font-family: "DM Mono", ui-monospace, monospace;
}}
.r-pipe-chip {{
    border: 1px solid {LINE_STRONG}; border-radius: 8px; padding: .32rem .55rem;
    color: {SAGE}; font-size: .8rem; line-height: 1.35; margin-top: .4rem;
}}
.r-pipe-link {{
    position: relative; align-self: center; height: 2px; background: {LINE_STRONG};
    margin: 0 .3rem;
}}
.r-pipe-link::after {{
    content: ""; position: absolute; right: -2px; top: -4px;
    border-left: 7px solid {LINE_STRONG}; border-top: 5px solid transparent;
    border-bottom: 5px solid transparent;
}}
.r-pipe-link::before {{
    content: ""; position: absolute; top: -1px; left: 0; width: 34%; height: 4px;
    border-radius: 2px; background: linear-gradient(90deg, transparent, {TAN});
    opacity: 0; animation: r-flow 3s linear 3 both;
    animation-delay: calc(1s + var(--i) * .75s);
}}
.r-pipe-label {{
    position: absolute; left: 0; right: 0; bottom: 9px; text-align: center;
    color: {MUTED}; font-size: .66rem; line-height: 1.25;
}}
@media (max-width: 900px) {{
    .r-pipe {{ grid-template-columns: 1fr; }}
    .r-pipe-node {{ min-height: 0; }}
    .r-pipe-link {{ width: 2px; height: 46px; margin: 0 auto; }}
    .r-pipe-link::after {{
        right: auto; left: -4px; top: auto; bottom: -2px; border-left: 5px solid transparent;
        border-right: 5px solid transparent; border-top: 7px solid {LINE_STRONG};
        border-bottom: 0;
    }}
    .r-pipe-link::before {{
        width: 4px; height: 34%; left: -1px; top: 0;
        background: linear-gradient(180deg, transparent, {TAN});
        animation-name: r-flow-down;
    }}
    .r-pipe-label {{ left: 14px; right: auto; bottom: auto; top: 14px; white-space: nowrap; }}
}}

/* Only real links answer the pointer: page links nudge their arrow, buttons step and press */
[data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"] {{
    transition: transform 120ms var(--r-ease);
}}
[data-testid="stPageLink-NavLink"]:hover span[data-testid="stIconMaterial"] {{
    transform: translateX(3px); transition-duration: 150ms;
}}
.stButton button, [data-testid="stFormSubmitButton"] button {{
    transition: transform 120ms var(--r-ease), background-color 150ms var(--r-ease);
}}
.stButton button:hover, [data-testid="stFormSubmitButton"] button:hover {{
    transform: translateY(-1px);
}}
.stButton button:active, [data-testid="stFormSubmitButton"] button:active {{
    transform: translateY(1px) scale(.985); transition-duration: 90ms;
}}

/* The assistant's shortcut, fixed in the corner of every other page */
.st-key-agent-fab {{
    position: fixed; right: 1.6rem; bottom: 1.5rem; z-index: 999990; width: auto !important;
}}
.st-key-agent-fab [data-testid="stPageLink-NavLink"] {{
    background: {RED}; border-radius: 999px; padding: .62rem 1.15rem .62rem .95rem;
    box-shadow: 0 10px 28px rgba(0, 0, 0, .45); gap: .45rem;
    transition: transform 150ms var(--r-ease), background-color 150ms var(--r-ease);
}}
.st-key-agent-fab [data-testid="stPageLink-NavLink"]:hover {{
    background: #b8302d; transform: translateY(-2px);
}}
.st-key-agent-fab [data-testid="stPageLink-NavLink"] p,
.st-key-agent-fab [data-testid="stPageLink-NavLink"] span {{
    color: {CREAM} !important; font-weight: 500;
}}

@keyframes r-rise {{ from {{ transform: translateY(105%); }} }}
@keyframes r-up {{ from {{ opacity: 0; transform: translateY(10px); }} }}
@keyframes r-count {{ from {{ --c: 0; }} }}
@keyframes r-flow {{
    0% {{ left: 0; opacity: 0; }} 15% {{ opacity: 1; }} 70% {{ opacity: 1; }}
    100% {{ left: 66%; opacity: 0; }}
}}
@keyframes r-flow-down {{
    0% {{ top: 0; opacity: 0; }} 15% {{ opacity: 1; }} 70% {{ opacity: 1; }}
    100% {{ top: 66%; opacity: 0; }}
}}
@keyframes r-node {{ 0%, 100% {{ border-color: {LINE}; }} 40% {{ border-color: {TAN}; }} }}

@media (prefers-reduced-motion: reduce) {{
    .r-head-icon, .r-w > span, .r-purpose, .r-statement, .r-fact, .r-c, .r-pipe-node {{
        animation: none;
    }}
    .r-pipe-link::before {{ display: none; }}
}}
"""

# Leading number of a formatted value ("204.408", "77,2%", "+3 p.p."), kept apart from the rest
NUMBER = re.compile(r"([+-]?)(\d{1,3}(?:\.\d{3})*)(,\d+)?(\D*)")
# Numbers to highlight inside a statement are written between double brackets: [[204.408]]
MARKED = re.compile(r"\[\[(.+?)\]\]")


@dataclass
class Stat:
    value: str
    label: str
    note: str = ""


@dataclass
class Stage:
    tag: str
    name: str
    text: str = ""
    figure: str = ""
    chips: list[str] = field(default_factory=list)


def apply_theme() -> None:
    st.html(f"<style>{CSS}</style>")


# The integer part counts up; groups after the first are padded to three digits ("204.008")
def counting(value: str) -> str:
    match = NUMBER.fullmatch(value)
    if match is None:
        return escape(value)
    sign, integer, decimals, rest = match.groups()
    first, *groups = integer.split(".")
    parts = [f'<span class="r-c" style="--c:{int(first)}"></span>']
    parts += [f'.<span class="r-c r-c3" style="--c:{int(group)}"></span>' for group in groups]
    return escape(sign) + "".join(parts) + escape(decimals or "") + escape(rest)


# `icon` is a Material Symbols name, the same one the page uses in the navigation
def header(title: str, purpose: str, icon: str) -> None:
    words = " ".join(
        f'<span class="r-w"><span style="--i:{index}">{escape(word)}</span></span>'
        for index, word in enumerate(title.split())
    )
    st.html(
        f'<header class="r-head"><span class="r-head-icon" aria-hidden="true">{escape(icon)}'
        f'</span><div><h1 class="r-title" aria-label="{escape(title)}">{words}</h1>'
        f'<p class="r-purpose">{escape(purpose)}</p></div></header>'
    )


def statement(text: str) -> None:
    parts = MARKED.split(text)
    html = "".join(
        f'<span class="r-hl">{counting(part)}</span>' if index % 2 else escape(part)
        for index, part in enumerate(parts)
    )
    st.html(f'<p class="r-statement">{html}</p>')


def facts(items: list[Stat]) -> None:
    cells = "".join(
        f'<div class="r-fact" style="--i:{index}">'
        f'<div class="r-fact-value" aria-label="{escape(item.value)}">'
        f"{counting(item.value)}</div>"
        f'<div class="r-fact-label">{escape(item.label)}</div>'
        + (f'<div class="r-fact-note">{escape(item.note)}</div>' if item.note else "")
        + "</div>"
        for index, item in enumerate(items)
    )
    st.html(f'<div class="r-facts">{cells}</div>')


def group(title: str, note: str = "") -> None:
    note_html = f"<p>{escape(note)}</p>" if note else ""
    st.html(f'<div class="r-group"><h2>{escape(title)}</h2>{note_html}</div>')


# Section titles state the takeaway; the note says how to read the chart below it
def section(title: str, note: str = "") -> None:
    note_html = f"<p>{escape(note)}</p>" if note else ""
    st.html(f'<div class="r-section"><h3>{escape(title)}</h3>{note_html}</div>')


@contextmanager
def panel(key: str, height: int | None = None):
    if height:
        with st.container(border=True, key=f"pfixed-{key}", height=height):
            yield
    else:
        with st.container(border=True, key=f"panel-{key}"):
            yield


def panel_title(place: str, name: str) -> None:
    place_html = f'<p class="r-panel-place">{escape(place)}</p>' if place else ""
    st.html(f'{place_html}<p class="r-panel-name">{escape(name)}</p>')


def callout(text: str) -> None:
    st.html(f'<div class="r-callout">{escape(text)}</div>')


def note(text: str) -> None:
    st.html(f'<p class="r-note">{escape(text)}</p>')


# Stages from left to right; `links` holds the label of each arrow between two stages
def pipeline_flow(stages: list[Stage], links: list[str]) -> None:
    parts = []
    for index, stage in enumerate(stages):
        chips = "".join(f'<div class="r-pipe-chip">{escape(chip)}</div>' for chip in stage.chips)
        figure = f'<div class="r-pipe-figure">{escape(stage.figure)}</div>' if stage.figure else ""
        text = f'<div class="r-pipe-text">{escape(stage.text)}</div>' if stage.text else ""
        parts.append(
            f'<div class="r-pipe-node" style="--i:{index}">'
            f'<div class="r-pipe-tag">{escape(stage.tag)}</div>'
            f'<div class="r-pipe-name">{escape(stage.name)}</div>{text}{chips}{figure}</div>'
        )
        if index < len(links):
            parts.append(
                f'<div class="r-pipe-link" style="--i:{index}" aria-hidden="true">'
                f'<span class="r-pipe-label">{escape(links[index])}</span></div>'
            )
    st.html(f'<div class="r-pipe">{"".join(parts)}</div>')


# Short definitions for readers who do not know the city or the service
def glossary(terms: list[tuple[str, str]]) -> None:
    items = "".join(
        f'<div class="r-term"><div class="r-term-name">{escape(term)}</div>'
        f'<div class="r-term-text">{escape(text)}</div></div>'
        for term, text in terms
    )
    st.html(f'<div class="r-terms">{items}</div>')
