"""The interior lava patch follows the plan's theme (step 35 task 2, Req 3; archive decision 3).

Off unless the plan's element is lava or its dungeon theme is ``lava_forge``; off, the
patch's cell is plains and every other cell is as it was with the patch."""

from __future__ import annotations

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.wilderness.build import landscape_for, wilderness_spec
from generators.wilderness.matrix import EdgeConnection, build_matrix, wants_lava


def _kinds(m):
    return [[c.node_type for c in row] for row in m.cells]


def test_only_a_lava_theme_wants_lava():
    assert wants_lava("lava", "")
    assert wants_lava("", "lava_forge")
    assert wants_lava(None, "lava_forge")
    for tint, theme in (("", ""), (None, None), ("ice", ""), ("water", "tomb"), ("", "ice_keep")):
        assert not wants_lava(tint, theme)


@pytest.mark.parametrize("seed", [1, 3, 7, 42, 1955208177])
def test_off_by_default_and_off_changes_only_the_patch(seed):
    edges = [EdgeConnection(side="S", edge_type="river")] if seed % 2 else None
    off = build_matrix("plains", edges, seed)
    on = build_matrix("plains", edges, seed, lava=True)
    assert _kinds(off) == _kinds(build_matrix("plains", edges, seed, lava=False))
    a, b = _kinds(off), _kinds(on)
    assert not any("lava" in row for row in a)
    patch = [(i, j) for i, row in enumerate(b) for j, k in enumerate(row) if k == "lava"]
    assert patch, "a lava theme draws the patch"
    for i, row in enumerate(b):
        for j, k in enumerate(row):
            assert a[i][j] == ("plains" if (i, j) in patch else k), (i, j)


def test_the_spec_records_lava_only_when_on():
    plain = wilderness_spec("z", 5)
    lava = wilderness_spec("z", 5, lava=True)
    assert "lava" not in plain.wilderness
    assert lava.wilderness["lava"] is True
    assert not any(r.kind == "lava" for r in plain.regions)
    assert any(r.kind == "lava" for r in lava.regions)
    assert "lava" in landscape_for(lava).synth.node_type
    assert "lava" not in landscape_for(plain).synth.node_type


def test_a_plan_carries_its_theme_to_the_patch():
    hot = plan_to_spec(ZonePlan(name="z", zone_type="wilderness", elemental_tint="lava"), seed=5)
    cold = plan_to_spec(ZonePlan(name="z", zone_type="wilderness"), seed=5)
    assert hot.wilderness.get("lava") is True
    assert "lava" not in cold.wilderness


def test_an_area_world_without_lava_is_not_reused_for_a_lava_spec():
    from generators.outdoor_dungeon import AREA_ATTR, area_world

    spec = wilderness_spec("z", 5)
    setattr(spec, AREA_ATTR, area_world(spec))
    spec.wilderness["lava"] = True
    world = area_world(spec)
    assert world.recipe.get("lava") is True
    assert "lava" in world.terrain.node_type
