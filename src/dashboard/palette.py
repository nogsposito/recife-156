"""Every colour of the dashboard lives here.

Change a value below and the charts, maps and page styles follow. The Streamlit theme in
.streamlit/config.toml repeats the base colours (it cannot import Python), and
tests/test_palette.py fails if the two drift apart.
"""

# Base
BACKGROUND = "#080f0f"  # page ground
SURFACE = "#0f1818"  # panels
LINE = "#1d2928"  # borders and chart grid
TEXT = "#f2f5f5"  # titles, numbers and body text
TEXT_SOFT = "#b8c2c2"  # secondary text
TEXT_MUTED = "#7d8a8a"  # notes and axis titles

# Data roles
PRIMARY = "#4a86c5"  # blue: what each chart is about
SECONDARY = "#6aa57c"  # sage green: comparisons and context
ALERT = "#a52422"  # red: delays, old tickets, a growing queue


def rgb(color: str) -> list[int]:
    color = color.lstrip("#")
    return [int(color[index : index + 2], 16) for index in (0, 2, 4)]


def rgba(color: str, alpha: float) -> str:
    red, green, blue = rgb(color)
    return f"rgba({red}, {green}, {blue}, {alpha})"


# `share` of `other` mixed into `color`: 0 keeps `color`, 1 gives `other`
def mix(color: str, other: str, share: float) -> str:
    return "#" + "".join(
        f"{round(a + (b - a) * share):02x}" for a, b in zip(rgb(color), rgb(other), strict=True)
    )


def ramp(start: str, end: str, steps: int) -> list[str]:
    return [mix(start, end, index / (steps - 1)) for index in range(steps)]


# Derived colours, so the rest of the code never writes a hex value of its own
LINE_STRONG = mix(LINE, TEXT, 0.12)
ALERT_HOVER = mix(ALERT, TEXT, 0.12)
# Magnitude (heatmaps, the neighborhood map): dark blue for little, the full blue for a lot.
# The brightest step stays dark enough for white text on top of it.
MAGNITUDE = ramp(mix(BACKGROUND, PRIMARY, 0.15), PRIMARY, 7)
# Columns of the 3D map, from dark to light blue
COLUMNS = ramp(mix(BACKGROUND, PRIMARY, 0.35), mix(PRIMARY, TEXT, 0.55), 6)
