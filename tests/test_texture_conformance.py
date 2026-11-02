"""Conformance and the recipe texture mode (interesting textures spec task 6,
Req 4.4, 5, 7; property Y5).

Recipe textures are graded into the theme's classic Look_Stats band (except a
family's listed exemptions); dungeon and city builds draw them by default and
record family and Look_Stats; placeholder and ai still work by override;
wilderness surfaces and trees are as in step 3; and procedural textures are
the same in any process.
"""

import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

import generators.textures.painters.natural  # noqa: F401
from ai.expand import plan_to_spec
from ai.planner import make_plan
from ai.schema import ZonePlan
from core.eqg import dds_to_rgb
from core.pfs import PfsArchive
from generators.builder import ZoneBuilder
from generators.textures.base import TextureSpec
from generators.textures.conformance import (
    EXEMPT, LOOK_KEYS, grade, look_band, look_stats, out_of_band, theme_for)
from generators.textures.painters import paint, seed_for
from generators.textures.placeholder import placeholder_dds
from generators.textures.procedural import ProceduralProvider, RecipeProvider
from generators.textures.recipes import load_recipes, resolve
from tests.pbt_helpers import scaled

FAMILIES = sorted(load_recipes().families)


def _saturation(c):
    return (max(c) - min(c)) / max(max(c), 1)


# Tinted, earthy base colours, like every palette colour: today's palettes run
# from saturation 0.09 (city floor (130, 125, 118)) to 0.31 (lava forge wall
# (104, 82, 72)); the strategy allows 0.08-0.6. A neutral grey base has no hue
# to saturate, and near-pure neon primaries saturate past the band when their
# one bright channel clips; Req 5.1 lets a base colour outside the band keep
# that statistic (the neutral case is tested below).
COLOURS = st.tuples(*(st.integers(30, 220),) * 3).filter(
    lambda c: 0.08 <= _saturation(c) <= 0.6)


@settings(max_examples=scaled(40), deadline=None)
@given(family=st.sampled_from([f for f in FAMILIES if f not in EXEMPT]),
       theme=st.sampled_from(["dungeon", "city"]),
       colour=COLOURS, seed=st.integers(0, 2**31 - 1))
def test_y5_graded_textures_lie_in_the_classic_band(family, theme, colour, seed):
    params = load_recipes().families[family]
    stats = look_stats(grade(paint(family, params, colour, seed), theme, family))
    assert list(out_of_band(stats, theme, family)) == [], (family, theme, colour, stats)


def _palette_colours(family):
    """The base colours the recipes actually give an exempt family."""
    from generators import semantics
    pals = {**semantics._THEME_PALETTES, **semantics._TINT_PALETTES}
    out = []
    for key, pal in pals.items():
        for surface, (colour, _) in pal.items():
            r = resolve(f"{key}_{surface}")
            if r and r.family == family:
                out.append((key, colour))
    if family == "sky":
        out.append(("city", (120, 140, 170)))    # layout's city ceiling palette
    return out


@pytest.mark.parametrize("family", sorted(EXEMPT))
def test_y5_exempt_families_in_band_on_their_own_colours(family):
    """An exempt statistic is set by the material's own colour (pale ice, sky
    blue); on those colours every other statistic is in the band."""
    cases = _palette_colours(family)
    assert cases
    for key, colour in cases:
        theme = theme_for(key)
        rgb = grade(paint(family, load_recipes().families[family], colour, 1), theme, family)
        assert list(out_of_band(look_stats(rgb), theme, family)) == [], (key, colour)


def test_grading_moves_toward_the_classic_median():
    """A pale, grey texture comes out darker and more saturated, nearer the
    dungeon median than it went in."""
    params = load_recipes().families["dressed_stone"]
    raw = paint("dressed_stone", params, (170, 165, 160), 3)
    before, after = look_stats(raw), look_stats(grade(raw, "dungeon", "dressed_stone"))
    band = look_band("dungeon")
    for key in ("lum_mean", "saturation"):
        assert abs(after[key] - band[key]["p50"]) < abs(before[key] - band[key]["p50"])


def test_a_neutral_base_stays_neutral():
    """Req 5.1's base-colour exception: grading can't invent a hue, so a grey
    base keeps saturation 0 while its brightness and contrast are graded."""
    raw = paint("brick", load_recipes().families["brick"], (30, 30, 30), 1)
    stats = look_stats(grade(raw, "dungeon", "brick"))
    assert stats["saturation"] == 0
    assert list(out_of_band(stats, "dungeon", "brick")) == ["saturation"]


def test_exempt_families_keep_their_exempt_statistics():
    raw = paint("sky", load_recipes().families["sky"], (120, 140, 170), 5)
    assert np.array_equal(grade(raw, "city", "sky"), raw)
    assert set(EXEMPT) <= set(FAMILIES)


@pytest.mark.parametrize("name, theme", [("city_wall", "city"), ("city", "city"),
                                         ("gnoll_temple_wall", "dungeon"),
                                         ("dungeon_floor", "dungeon")])
def test_theme_for(name, theme):
    assert theme_for(name.rpartition("_")[0] or name) == theme


# ---------------------------------------------------------------------------
# Builds
# ---------------------------------------------------------------------------

SPECS = {
    "dungeon": lambda: plan_to_spec(make_plan("a gnoll temple dungeon with 8 rooms", name="conf"), seed=7),
    "city": lambda: plan_to_spec(ZonePlan(name="conf", zone_type="city"), seed=7),
    "wilderness": lambda: plan_to_spec(ZonePlan(name="conf", zone_type="wilderness"), seed=7,
                                       edges={"N": "zoneline", "E": "river"}),
}


def _build(tmp_path, kind, sub="a"):
    spec = SPECS[kind]()
    r = ZoneBuilder(spec).build(output_dir=tmp_path / f"{kind}_{sub}", write_glb=False)
    side = json.loads(r.sidecar_path.read_text(encoding="utf-8"))
    return spec, PfsArchive.from_file(r.eqg_path), side


@pytest.mark.parametrize("kind", ["dungeon", "city"])
def test_room_graph_builds_draw_recipe_textures_by_default(tmp_path, no_api_keys, kind):
    spec, arc, side = _build(tmp_path, kind)
    room = [e for e in side["textures"] if e["surface_class"]]
    assert room
    for e in room:
        recipe = resolve(e["material"])
        assert e["texture_mode"] == "procedural" and e["texture_family"] == recipe.family
        rgb = dds_to_rgb(arc.get(e["texture"]))
        stats = look_stats(rgb)
        assert e["look_stats"] == {k: round(v, 4) for k, v in stats.items()}
        assert list(out_of_band(stats, theme_for(e["texture_set"]), recipe.family)) == []
        colour = spec.materials[e["material"]].color
        want = grade(paint(recipe.family, recipe.params, colour, seed_for(e["material"])),
                     theme_for(e["texture_set"]), recipe.family)
        assert np.array_equal(rgb, want)


def test_wilderness_surfaces_and_trees_are_as_in_step_3(tmp_path, no_api_keys, monkeypatch):
    spec, arc, side = _build(tmp_path, "wilderness", "default")
    for e in side["textures"]:
        if e["surface_class"]:
            assert e["texture_mode"] == "placeholder" and "texture_family" not in e
            colour = spec.materials[e["material"]].color
            assert arc.get(e["texture"]) == placeholder_dds(e["material"], colour, e["surface_class"])
    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "procedural")
    _, noise_arc, _ = _build(tmp_path, "wilderness", "procedural")
    for e in side["textures"]:
        if e["texture_mode"] == "vegetation":
            assert arc.get(e["texture"]) == noise_arc.get(e["texture"])


def test_placeholder_override_still_draws_placeholders(tmp_path, no_api_keys, monkeypatch):
    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "placeholder")
    _, _, side = _build(tmp_path, "dungeon")
    assert {e["texture_mode"] for e in side["textures"]} == {"placeholder"}


def test_ai_override_without_a_key_falls_back_to_recipes(tmp_path, no_api_keys, monkeypatch):
    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "ai")
    _, _, side = _build(tmp_path, "city")
    assert all(e["texture_mode"] == "procedural" and e.get("texture_family")
               for e in side["textures"])


def test_unresolvable_names_fall_back_to_noise():
    spec = TextureSpec(name="wild_plains", base_color=(104, 132, 70), surface_class="ground")
    assert RecipeProvider().generate(spec) == ProceduralProvider().generate(spec)


def test_procedural_textures_are_the_same_in_a_fresh_process():
    """Req 4.4: recipe textures and the unseeded noise path (formerly seeded
    by the salted ``hash()``) give the same bytes under another hash seed."""
    cases = [("gnoll_temple_wall", (135, 122, 100), "wall"),
             ("city_ceiling", (120, 140, 170), "ceiling")]
    noise = ("wild_plains", (104, 132, 70), "")

    def digests():
        out = [hashlib.sha256(RecipeProvider().generate(
            TextureSpec(name=n, base_color=c, surface_class=s))).hexdigest() for n, c, s in cases]
        out.append(hashlib.sha256(ProceduralProvider().generate(
            TextureSpec(name=noise[0], base_color=noise[1]))).hexdigest())
        return out

    code = (
        "import hashlib\n"
        "from generators.textures.base import TextureSpec\n"
        "from generators.textures.procedural import ProceduralProvider, RecipeProvider\n"
        f"for n, c, s in {cases!r}:\n"
        "    print(hashlib.sha256(RecipeProvider().generate(TextureSpec(name=n, base_color=c, surface_class=s))).hexdigest())\n"
        f"print(hashlib.sha256(ProceduralProvider().generate(TextureSpec(name={noise[0]!r}, base_color={noise[1]!r}))).hexdigest())\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, env={**os.environ, "PYTHONHASHSEED": "99"})
    assert out.stdout.split() == digests()


# ---------------------------------------------------------------------------
# Task 10: recipe textures add at most 2 s (Req 8, Y7)
# ---------------------------------------------------------------------------

TEXTURE_BUDGET_S = 2.0


def _timed_build(tmp_path, sub):
    import time

    import generators.textures.factory as factory

    factory._cache.clear()
    spec = plan_to_spec(make_plan("a gnoll temple dungeon with 30 rooms", name="tbig"), seed=7)
    t0 = time.perf_counter()
    ZoneBuilder(spec).build(output_dir=tmp_path / sub)
    return time.perf_counter() - t0


@pytest.mark.slow
def test_y7_recipe_textures_add_at_most_2s(tmp_path, no_api_keys, monkeypatch):
    """A 30-room themed dungeon (EQG + GLB) in the default recipe mode against
    step 3's placeholders, texture cache cleared, best of two each."""
    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "placeholder")
    _timed_build(tmp_path, "warm")
    placeholder = min(_timed_build(tmp_path, f"p{i}") for i in range(2))
    monkeypatch.delenv("EQ_S3D_TEXTURE_PROVIDER")
    recipe = min(_timed_build(tmp_path, f"r{i}") for i in range(2))
    assert recipe - placeholder <= TEXTURE_BUDGET_S, (
        f"recipe build {recipe:.2f}s vs placeholder {placeholder:.2f}s: "
        f"{recipe - placeholder:.2f}s added (budget {TEXTURE_BUDGET_S:g}s)")
