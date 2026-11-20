"""The ``cave`` Purpose (step 21 task 1, zone-generator-cave Requirement 1)."""

from __future__ import annotations

import pytest

from ai.expand import plan_to_spec
from ai.schema import VALID_DUNGEON_THEMES, ZonePlan
from generators import semantics
from generators.topology.graph import ROOM_KINDS

CAVE_TYPES = ("cave_mouth", "cavern", "crystal_grotto", "grotto")


def _spec(theme, layout, rooms, seed):
    plan = ZonePlan(name="cv", room_count=rooms, layout=layout, dungeon_theme=theme)
    return plan_to_spec(plan.validate(), seed=seed)


def _cave_vocabulary():
    arch = semantics.ARCHETYPES["cave"]
    kinds = semantics.kind_types("cave")
    return ({arch.entrance_type, arch.hub_type, arch.climax_type, *arch.arc}
            | {t for types in kinds.values() for t in types})


def _mood(spec):
    """``(coldness, brightness)`` averaged over the lights: blue minus red, and the
    brightest channel."""
    lights = spec.lights
    assert lights
    cold = sum(lt.b - lt.r for lt in lights) / len(lights)
    bright = sum(max(lt.r, lt.g, lt.b) for lt in lights) / len(lights)
    return cold, bright


def test_cave_is_in_the_vocabulary():
    assert "cave" in semantics.ARCHETYPES and "cave" in VALID_DUNGEON_THEMES
    arch = semantics.ARCHETYPES["cave"]
    assert (arch.entrance_type, arch.hub_type, arch.climax_type) == (
        "cave_mouth", "cavern", "crystal_grotto")
    assert set(arch.arc) <= set(semantics.ROOM_TYPES)
    assert all(t in semantics.ROOM_TYPES for t in CAVE_TYPES)
    assert semantics.ROOM_TYPES["flooded_gallery"].region == "water"
    assert "cave" in semantics.PURPOSE_PALETTES


def test_cave_maps_every_kind():
    kmap = semantics.kind_types("cave")
    assert semantics.unmapped_kinds("cave", ROOM_KINDS) == []
    for kind in ROOM_KINDS:
        assert kmap[kind] and all(t in semantics.ROOM_TYPES for t in kmap[kind]), kind


def test_the_room_types_are_shaped_and_lit_as_designed():
    rt = semantics.ROOM_TYPES
    assert rt["cave_mouth"].footprint > 1.0 and rt["cave_mouth"].ceiling < 1.0
    assert rt["cavern"].footprint > 1.2 and rt["cavern"].ceiling > 1.2
    assert rt["crystal_grotto"].ceiling > 1.2
    assert rt["grotto"].footprint < 1.0 and rt["grotto"].ceiling < 1.0
    for name in CAVE_TYPES:
        r, _, b = rt[name].light
        assert b > r, name                                     # cool
    assert rt["crystal_grotto"].intensity > max(rt[n].intensity for n in CAVE_TYPES[:2] + CAVE_TYPES[3:])


def test_the_cave_palette_and_light_are_its_own():
    pal = semantics.PURPOSE_PALETTES["cave"]
    for other, p in semantics.PURPOSE_PALETTES.items():
        if other != "cave":
            assert p != pal, other
    cave_lights = {semantics.ROOM_TYPES[t].light for t in CAVE_TYPES}
    for name, t in semantics.ROOM_TYPES.items():
        if name not in CAVE_TYPES:
            assert t.light not in cave_lights, name


@pytest.mark.parametrize("layout", ["classic", "graph"])
@pytest.mark.parametrize("rooms", [8, 15, 30])
def test_a_cave_dungeon(layout, rooms):
    vocab = _cave_vocabulary()
    for seed in (1, 2, 3):
        spec = _spec("cave", layout, rooms, seed)
        where = (layout, rooms, seed)
        assert spec.dungeon_theme == "cave", where
        types = [r.semantic_type for r in spec.rooms]
        assert set(types) <= vocab, (where, set(types) - vocab)
        entrance = [r for r in spec.rooms if r.role == "entrance"]
        climax = [r for r in spec.rooms if r.role == "climax"]
        assert [r.semantic_type for r in entrance] == ["cave_mouth"], where
        assert [r.semantic_type for r in climax] == ["crystal_grotto"], where
        regions = {(g.id, g.kind) for g in spec.regions}
        for i, r in enumerate(spec.rooms):
            if r.semantic_type == "flooded_gallery":
                assert (f"water_{i}", "water") in regions, (where, r.id)

        cold, bright = _mood(spec)
        f_cold, f_bright = _mood(_spec("fortress", layout, rooms, seed))
        assert cold > f_cold and bright < f_bright, (where, cold, f_cold, bright, f_bright)
