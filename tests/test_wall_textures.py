"""Room walls task 10 (Requirement 9.1): a style's look reaches the materials. Rock styles
get rock in place of masonry, a theme's character is kept where it has one, and the
classic Look_Stats bands still hold.
"""

import pytest
from hypothesis import given, settings, strategies as st

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.semantics import _THEME_PALETTES
from generators.textures.conformance import grade, look_stats, out_of_band
from generators.textures.painters import paint
from generators.textures.recipes import load_recipes, resolve
from generators.wall_styles import MASONRY


PALETTE_COLOURS = sorted({colour for palette in _THEME_PALETTES.values() for colour, _desc in palette.values()})


def _spec(theme="", walls="", race="", seed=4):
    return plan_to_spec(ZonePlan(name="w10", zone_type="dungeon", room_count=10, layout="graph", walls=walls,
                                 dungeon_theme=theme, dungeon_race=race).validate(), seed=seed)


def _families(spec, surface):
    holders = spec.rooms + spec.corridors
    return {resolve(getattr(h, f"{surface}_material")).family for h in holders}


def test_rough_is_rock_on_every_surface():
    spec = _spec(walls="rough")
    for surface in ("wall", "floor", "ceiling"):
        assert _families(spec, surface) == {"cave_rock"}, surface


def test_hewn_keeps_its_laid_floor():
    spec = _spec(walls="hewn")
    assert _families(spec, "wall") == {"cave_rock"}
    assert _families(spec, "floor") <= set(MASONRY)


def test_built_is_untouched_masonry():
    spec = _spec(walls="built")
    assert _families(spec, "wall") <= set(MASONRY)
    assert not any("_rock_" in name for name in spec.materials)


def test_a_themes_character_stays():
    """An ice keep's walls stay ice under Rough; a lava forge's basalt stays basalt."""
    assert _families(_spec("ice_keep", "rough"), "wall") == {"ice"}
    spec = _spec("lava_forge", "rough")
    assert _families(spec, "wall") == {"cave_rock"}
    assert not any("_rock_" in r.wall_material for r in spec.rooms), "its basalt, not generic rock"


def test_a_themes_colour_carries_over():
    plain, rough = _spec("temple", "built"), _spec("temple", "rough")
    colour = plain.materials[plain.rooms[0].wall_material].color
    assert rough.materials[rough.rooms[0].wall_material].color == colour


def test_names_stay_readable_and_nothing_unused_is_packed():
    spec = _spec("temple", "rough", race="gnoll")
    used = {getattr(h, f"{s}_material") for h in spec.rooms + spec.corridors for s in ("floor", "wall", "ceiling")}
    assert set(spec.materials) == used
    assert "gnoll_temple_rock_wall" in used
    for name, material in spec.materials.items():
        assert material.texture == f"{name}.dds"


def test_rock_recipes_are_found_by_theme():
    for surface in ("wall", "floor", "ceiling"):
        recipe = resolve(f"dungeon_rock_{surface}")
        assert (recipe.family, recipe.source) == ("cave_rock", "theme")
    assert resolve("gnoll_temple_rock_floor").params["scale"] == 6


@settings(max_examples=20, deadline=None)
@given(surface=st.sampled_from(["wall", "floor", "ceiling"]), seed=st.integers(0, 2 ** 31 - 1),
       colour=st.sampled_from(PALETTE_COLOURS))
def test_rock_lies_in_the_classic_band(surface, seed, colour):
    """Over the colours materials really have (a neutral grey can't take on saturation)."""
    recipe = resolve(f"dungeon_rock_{surface}")
    stats = look_stats(grade(paint(recipe.family, recipe.params, colour, seed), "dungeon", recipe.family))
    assert list(out_of_band(stats, "dungeon", recipe.family)) == [], stats


def test_recipe_file_still_parses():
    assert "cave_rock" in load_recipes().families


@pytest.mark.parametrize("theme", ["warren", "mine_delve"])
def test_a_rock_theme_gets_rock_walls_from_theme(theme):
    assert _families(_spec(theme), "wall") == {"cave_rock"}
