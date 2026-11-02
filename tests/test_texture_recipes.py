"""Texture recipes (interesting textures spec task 3, Req 3, property Y3).

Every dungeon and city Material_Name a build can produce resolves to a
family; names with no entry fall back by Surface and say so; themes with
different palettes get different recipes; a bad file fails naming the field.
The names come from the code that makes them, not a list written here.
"""

import copy
import json

import pytest

from generators import semantics
from generators.textures.recipes import (
    RECIPES_PATH, RecipeError, load_recipes, parse_recipes, resolve)

SURFACES = ("floor", "wall", "ceiling")
THEMED_SURFACES = ("floor", "wall")   # semantics._apply_materials themes these
THEME_KEYS = sorted(set(semantics._THEME_PALETTES) | set(semantics._TINT_PALETTES))


def buildable_names():
    """{Material_Name: (zone_type, key or None, surface)} for every dungeon
    and city material the layout and semantics code can register."""
    names = {}
    for zone_type in ("dungeon", "city"):
        for race in [""] + sorted(semantics.RACE_SCALE):
            shared = semantics.texture_set(zone_type, race)
            for s in SURFACES:
                names[semantics.material_name(shared, s)] = (zone_type, None, s)
            for key in THEME_KEYS:
                tex_set = semantics.texture_set(zone_type, race, key)
                for s in THEMED_SURFACES:
                    names[semantics.material_name(tex_set, s)] = (zone_type, key, s)
    return names


def _palette(key, surface):
    pal = semantics._TINT_PALETTES.get(key) or semantics._THEME_PALETTES.get(key)
    return pal[surface][0] if pal and surface in pal else None


def test_y3_every_buildable_name_resolves():
    book = load_recipes()
    names = buildable_names()
    assert len(names) > 200   # 253 today: 10 races x (3 shared + 10 keys x 2) + city
    for name, (_, _, surface) in names.items():
        r = book.resolve(name)
        assert r is not None, name
        assert r.family in book.families
        assert r.source in ("set", "theme", "fallback")
        assert set(book.families[r.family]) <= set(r.params)


def test_every_theme_and_the_shared_sets_have_entries():
    """No buildable name needs the fallback today; the fallback is for names a
    future archetype adds before its recipe."""
    fallbacks = [n for n in buildable_names() if resolve(n).source == "fallback"]
    assert fallbacks == []


def test_unknown_names_fall_back_by_surface_and_say_so():
    book = load_recipes()
    for surface, family in book.fallback.items():
        r = book.resolve(f"orc_newtheme_{surface}")
        assert (r.family, r.source) == (family, "fallback")


@pytest.mark.parametrize("name", ["wild_plains", "liquid_water", "veg_conifer_leaf",
                                  "floor", "gnoll_temple_roof"])
def test_non_room_graph_names_resolve_to_none(name):
    assert resolve(name) is None


def test_most_specific_entry_wins():
    assert resolve("city_ceiling").source == "set"
    r = resolve("gnoll_wizard_lair_wall")
    assert (r.family, r.source) == ("brick", "theme")
    assert resolve("temple_wall") == resolve("ogre_temple_wall")


def test_themes_with_different_palettes_get_different_recipes():
    """Req 3.2: the same Surface under two themes (or the shared set) whose
    palette colours differ resolves to a different family or parameters."""
    for surface in THEMED_SURFACES:
        recipes = {}
        for key in THEME_KEYS:
            recipes[key] = (_palette(key, surface), resolve(f"{key}_{surface}"))
        recipes["dungeon"] = (None, resolve(f"dungeon_{surface}"))
        keys = sorted(recipes)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                (pa, ra), (pb, rb) = recipes[a], recipes[b]
                if pa != pb:
                    assert (ra.family, ra.params) != (rb.family, rb.params), (surface, a, b)


def _doc():
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("mutate, needle", [
    (lambda d: d.pop("families"), "families"),
    (lambda d: d["materials"][0].update(family="marble"), "materials[0].family"),
    (lambda d: d["materials"][1].update(surface="roof"), "materials[1].surface"),
    (lambda d: d["materials"][2].pop("theme"), "materials[2]"),
    (lambda d: d["materials"][0]["params"].update(sparkle=1), "materials[0].params"),
    (lambda d: d["fallback"].pop("ceiling"), "fallback.ceiling"),
])
def test_malformed_recipes_name_the_field(mutate, needle):
    doc = copy.deepcopy(_doc())
    mutate(doc)
    with pytest.raises(RecipeError, match=__import__("re").escape(needle)):
        parse_recipes(doc)
