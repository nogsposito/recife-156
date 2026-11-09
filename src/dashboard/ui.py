import re
from dataclasses import dataclass
from html import escape

import streamlit as st

from src.dashboard.style import INK, INK_2, MUTED

ACCENT_UI = "#5ab9fc"
SURFACE = "#131824"
LINE = "#232a38"
LINE_STRONG = "#3a465e"

CSS = f"""
:root {{
    --r-ease: cubic-bezier(.2, .8, .2, 1);
    --r-ease-enter: cubic-bezier(.22, 1, .36, 1);
}}
[data-testid="stAppViewContainer"] {{
    background:
        radial-gradient(900px 420px at 78% -8%, rgba(90, 185, 252, .10), transparent 65%),
        radial-gradient(700px 360px at 8% 0%, rgba(25, 158, 112, .05), transparent 60%),
        #0a0d14;
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ max-width: 1180px; padding-top: 3.6rem; }}
h1, h2, h3 {{ letter-spacing: -0.02em; color: {INK}; }}
[data-testid="stSidebarNav"] span {{ font-size: 0.93rem; }}

.r-kicker {{
    color: {ACCENT_UI}; font-family: "DM Mono", ui-monospace, monospace; font-size: 0.74rem;
    letter-spacing: 0.08em; text-transform: uppercase; margin: 0 0 0.6rem;
    animation: r-up .52s var(--r-ease-enter) both;
}}
.r-title {{
    font-size: clamp(2rem, 1.2rem + 2.4vw, 2.9rem); font-weight: 500; line-height: 1.08;
    color: {INK}; letter-spacing: -0.035em; margin: 0 0 0.9rem; max-width: 22ch;
}}
.r-w {{ display: inline-block; overflow: hidden; vertical-align: bottom; padding-bottom: .1em; }}
.r-w > span {{
    display: inline-block; animation: r-rise .7s var(--r-ease-enter) both;
    animation-delay: calc(var(--i) * 30ms);
}}
.r-lede {{
    font-size: 1.06rem; line-height: 1.6; color: {INK_2}; max-width: 68ch; margin: 0;
    animation: r-up .52s var(--r-ease-enter) .28s both;
}}

.r-section {{ margin: 2.2rem 0 0.3rem; }}
.r-section h3 {{ font-size: 1.28rem; font-weight: 500; margin: 0 0 0.3rem; padding: 0; }}
.r-section p {{
    color: {INK_2}; font-size: 0.95rem; line-height: 1.55; margin: 0; max-width: 78ch;
}}

.r-stats {{
    display: grid; gap: 0.75rem; margin: 1.6rem 0 0.4rem;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
}}
.r-stat {{
    background: {SURFACE}; border: 1px solid {LINE}; border-radius: 12px;
    padding: 1rem 1.1rem 1.05rem;
    transition: transform 120ms var(--r-ease), border-color 120ms var(--r-ease);
    animation: r-up .52s var(--r-ease-enter) both;
    animation-delay: calc(.34s + var(--i) * 60ms);
}}
.r-stat:hover {{
    transform: translateY(-2px); border-color: {LINE_STRONG};
    transition-duration: 180ms;
}}
.r-stat-value {{
    font-size: 2rem; font-weight: 500; color: {INK}; line-height: 1.1;
    letter-spacing: -0.03em;
}}
.r-stat-label {{ font-size: 0.88rem; color: {INK_2}; margin-top: 0.3rem; line-height: 1.35; }}
.r-stat-note {{
    font-size: 0.76rem; color: {MUTED}; margin-top: 0.4rem; line-height: 1.35;
    font-family: "DM Mono", ui-monospace, monospace;
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

.r-callout {{
    border-left: 2px solid {ACCENT_UI}; background: rgba(90, 185, 252, .07);
    border-radius: 0 10px 10px 0; padding: 0.8rem 1.05rem; color: {INK};
    font-size: 0.96rem; line-height: 1.55; margin: 0.9rem 0;
}}
.r-note {{ color: {MUTED}; font-size: 0.8rem; line-height: 1.5; margin: 0.2rem 0 0.6rem; }}

.r-flow {{
    display: grid; gap: 0.6rem; margin: 1rem 0 0.4rem;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
}}
.r-step {{
    background: {SURFACE}; border: 1px solid {LINE}; border-radius: 12px;
    padding: 0.9rem 1rem; position: relative; overflow: hidden;
    transition: transform 120ms var(--r-ease), border-color 120ms var(--r-ease);
}}
.r-step:hover {{
    transform: translateY(-2px); border-color: {LINE_STRONG}; transition-duration: 180ms;
}}
/* A pulse travels along the top edge of each step, one after the other, like data moving */
.r-step::before {{
    content: ""; position: absolute; top: 0; left: -40%; width: 40%; height: 2px;
    background: linear-gradient(90deg, transparent, {ACCENT_UI}, transparent);
    animation: r-pulse 3.2s linear 3 both; animation-delay: calc(1s + var(--i) * .64s);
}}
.r-step-tag {{
    font-size: 0.7rem; color: {ACCENT_UI}; letter-spacing: 0.08em;
    font-family: "DM Mono", ui-monospace, monospace;
}}
.r-step-name {{ font-size: 1.02rem; font-weight: 500; color: {INK}; margin: 0.2rem 0 0.4rem; }}
.r-step ul {{
    margin: 0; padding-left: 1rem; color: {INK_2}; font-size: 0.85rem; line-height: 1.5;
}}
.r-step-figure {{
    font-size: 0.82rem; color: {INK}; margin-top: 0.5rem;
    font-family: "DM Mono", ui-monospace, monospace;
}}

/* Bordered containers and links answer the pointer */
[data-testid="stVerticalBlockBorderWrapper"], .stVerticalBlock[data-testid] {{
    transition: transform 120ms var(--r-ease), border-color 120ms var(--r-ease);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(a):hover {{
    transform: translateY(-2px); border-color: {LINE_STRONG}; transition-duration: 180ms;
}}
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

@keyframes r-rise {{ from {{ transform: translateY(105%); }} }}
@keyframes r-up {{ from {{ opacity: 0; transform: translateY(10px); }} }}
@keyframes r-count {{ from {{ --c: 0; }} }}
@keyframes r-pulse {{ 0% {{ left: -40%; }} 35%, 100% {{ left: 100%; }} }}

@media (prefers-reduced-motion: reduce) {{
    .r-kicker, .r-w > span, .r-lede, .r-stat, .r-c {{ animation: none; }}
    .r-step::before {{ display: none; }}
}}
"""

# Leading number of a formatted value ("204.408", "77,2%", "+3 p.p."), kept apart from the rest
NUMBER = re.compile(r"([+-]?)(\d{1,3}(?:\.\d{3})*)(,\d+)?(\D*)")


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


def header(kicker: str, title: str, lede: str = "") -> None:
    words = " ".join(
        f'<span class="r-w"><span style="--i:{index}">{escape(word)}</span></span>'
        for index, word in enumerate(title.split())
    )
    lede_html = f'<p class="r-lede">{escape(lede)}</p>' if lede else ""
    st.html(
        f'<p class="r-kicker">{escape(kicker)}</p>'
        f'<h1 class="r-title" aria-label="{escape(title)}">{words}</h1>{lede_html}'
    )


# Section titles state the takeaway; the note says how to read the chart below it
def section(title: str, note: str = "") -> None:
    note_html = f"<p>{escape(note)}</p>" if note else ""
    st.html(f'<div class="r-section"><h3>{escape(title)}</h3>{note_html}</div>')


def stats(items: list[Stat]) -> None:
    cards = "".join(
        f'<div class="r-stat" style="--i:{index}">'
        f'<div class="r-stat-value" aria-label="{escape(item.value)}">'
        f"{counting(item.value)}</div>"
        f'<div class="r-stat-label">{escape(item.label)}</div>'
        + (f'<div class="r-stat-note">{escape(item.note)}</div>' if item.note else "")
        + "</div>"
        for index, item in enumerate(items)
    )
    st.html(f'<div class="r-stats">{cards}</div>')


def callout(text: str) -> None:
    st.html(f'<div class="r-callout">{escape(text)}</div>')


def note(text: str) -> None:
    st.html(f'<p class="r-note">{escape(text)}</p>')


def flow(steps: list[Step]) -> None:
    cards = "".join(
        f'<div class="r-step" style="--i:{index}"><div class="r-step-tag">{escape(step.tag)}</div>'
        f'<div class="r-step-name">{escape(step.name)}</div>'
        "<ul>"
        + "".join(f"<li>{escape(item)}</li>" for item in step.items)
        + "</ul>"
        + (f'<div class="r-step-figure">{escape(step.figure)}</div>' if step.figure else "")
        + "</div>"
        for index, step in enumerate(steps)
    )
    st.html(f'<div class="r-flow">{cards}</div>')
