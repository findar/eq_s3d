"""Texture_Profile in the style profiles (interesting textures spec task 2,
Req 2, property Y2).

The shipped profiles carry a measured ``textures`` block (texel density per
surface, Look_Stats bands) in place of the old always-1.0 ``uv.scale``; the
measurement is deterministic; and the dungeon numbers agree with the step 4
design's research table.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from analyzer.style_builder import LOOK_KEYS, SURFACES, look_stats, texture_profile
from core.env import env_value

STYLES = Path(__file__).resolve().parent.parent / "styles"
THEMES = ("dungeon", "city", "outdoor", "cave")

# Look_Stats medians from the step 4 design's research table (1,087 textures
# from 15 classic zones; a different but overlapping zone set).
RESEARCH_LOOK_P50 = {"lum_mean": 0.228, "lum_std": 0.076, "saturation": 0.406,
                     "edge_energy": 0.028}


def _profile(theme):
    return json.loads((STYLES / f"{theme}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("theme", THEMES)
def test_profiles_carry_a_measured_textures_block(theme):
    prof = _profile(theme)
    assert "uv" not in prof
    tex = prof["textures"]
    assert tex["textures_measured"] > 100 and tex["zones"]
    for surface in SURFACES:
        d = tex["texel_density"][surface]
        assert 0 < d["p25"] <= d["p50"] <= d["p75"]
    for key in LOOK_KEYS:
        band = tex["look"][key]
        assert 0 <= band["p10"] <= band["p50"] <= band["p90"]


def test_dungeon_profile_agrees_with_the_research():
    tex = _profile("dungeon")["textures"]
    # The research put per-zone dungeon wall medians at 12-24 u; the pooled
    # median over the reference zones (which include the coarser chardok and
    # velketor) lands at the top of that range.
    assert 12.0 <= tex["texel_density"]["wall"]["p50"] <= 24.5
    for key, research in RESEARCH_LOOK_P50.items():
        assert tex["look"][key]["p50"] == pytest.approx(research, rel=0.2), key


def test_look_stats_on_known_images():
    grey = np.full((256, 256, 3), 128, dtype=np.uint8)
    s = look_stats(grey)
    assert s["lum_std"] == 0 and s["edge_energy"] == 0 and s["saturation"] == 0
    red = np.zeros((256, 256, 3), dtype=np.uint8)
    red[..., 0] = 200
    assert look_stats(red)["saturation"] == pytest.approx(1.0)
    stripes = np.zeros((256, 256, 3), dtype=np.uint8)
    stripes[:, ::2] = 255
    assert look_stats(stripes)["edge_energy"] == pytest.approx(0.5, abs=1e-3)


def test_y2_measurement_is_deterministic():
    eq = env_value("EQ_PATH")
    if not eq or not (Path(eq) / "najena.s3d").exists():
        pytest.skip("needs EQ_PATH with najena.s3d")
    zones = ["najena", "befallen"]
    a = json.dumps(texture_profile(eq, zones), indent=2)
    b = json.dumps(texture_profile(eq, zones), indent=2)
    assert a == b
