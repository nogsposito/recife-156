import tomllib

from src.config import PROJECT_ROOT
from src.dashboard import palette
from src.dashboard.style import SERIES


def test_streamlit_theme_uses_the_palette_colours():
    config = tomllib.loads((PROJECT_ROOT / ".streamlit" / "config.toml").read_text("utf-8"))
    theme = config["theme"]

    assert theme["primaryColor"] == palette.PRIMARY
    assert theme["linkColor"] == palette.PRIMARY
    assert theme["backgroundColor"] == palette.BACKGROUND
    assert theme["secondaryBackgroundColor"] == palette.SURFACE
    assert theme["textColor"] == palette.TEXT
    assert theme["borderColor"] == palette.LINE
    assert theme["dataframeHeaderBackgroundColor"] == palette.SURFACE
    assert theme["chartCategoricalColors"] == SERIES
    assert theme["sidebar"]["backgroundColor"] == palette.BACKGROUND
    assert theme["sidebar"]["secondaryBackgroundColor"] == palette.SURFACE


def test_mix_and_ramp_go_from_one_colour_to_the_other():
    assert palette.mix("#000000", "#ffffff", 0.5) == "#808080"
    assert palette.ramp("#000000", "#ffffff", 3) == ["#000000", "#808080", "#ffffff"]
    assert palette.rgba("#4a86c5", 0.5) == "rgba(74, 134, 197, 0.5)"
