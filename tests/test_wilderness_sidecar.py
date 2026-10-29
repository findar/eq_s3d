"""Wilderness advisory data in the ``.zone.json`` sidecar (wilderness spec task 8).

A wilderness build's sidecar carries the biome (and the fallback record when
one fired), the edge declaration, the Invisible_Wall boxes, the damaging lava
regions, per-region intent and the POI anchors. It is advisory only: none of it
reaches the ``.eqg``, and room-graph sidecars gain no new key.
"""

from __future__ import annotations

import json

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder

WILD_KEYS = {"biome", "biome_substitution", "edge_connections",
             "invisible_walls", "lava", "region_intent", "poi_anchors"}


def _build(tmp_path, plan, **kw):
    spec = plan_to_spec(plan, seed=1337, **kw)
    result = ZoneBuilder(spec).build(output_dir=tmp_path)
    return spec, result, json.loads(result.sidecar_path.read_text())


@pytest.fixture
def karana(tmp_path):
    plan = ZonePlan(name="karana", zone_type="wilderness",
                    prompt="the rolling plains of the karanas")
    return _build(tmp_path, plan, edges={"N": "zoneline", "E": "river"})


def test_wilderness_sidecar_carries_the_advisory_data(karana):
    spec, result, data = karana
    assert data["biome"] == "plains"
    assert "biome_substitution" not in data  # plains asked for, plains given
    assert data["edge_connections"] == {
        "N": "zoneline", "E": "river", "S": "mountain", "W": "mountain"}

    (wall,) = data["invisible_walls"]
    assert wall["kind"] == "invisible_wall" and wall["side"] == "E"
    assert all(lo < hi for lo, hi in zip(wall["min_xy"], wall["max_xy"]))

    assert data["lava"], "seed 1337 places an interior lava patch"
    assert all(r["damaging"] is True for r in data["lava"])

    intent = {r["region_id"]: r["intent"] for r in data["region_intent"]}
    assert set(intent) == {r.id for r in spec.regions}
    assert intent["zoneline_N_0"] == "playable"
    assert intent[wall["region_id"]] == "scenic"
    assert all(intent[r["region_id"]] == "scenic" for r in data["lava"])

    (spawn,) = [a for a in data["poi_anchors"] if a["is_spawn"]]
    assert spawn["name"] == "Spawn" and spawn["intent"] == "playable"
    assert [spawn["x"], spawn["y"], spawn["z"]] == pytest.approx(list(spec.safe_point))


def test_glb_sidecar_matches_and_the_binary_carries_none_of_it(karana):
    _, result, data = karana
    # The GLB path and the standalone writer target the same file; the GLB
    # writer is handed the same keys, so both writes agree.
    assert result.glb_path is not None
    assert result.glb_path.with_suffix("").with_suffix(".zone.json") == result.sidecar_path
    blob = result.eqg_path.read_bytes()
    for marker in (b"invisible_wall", b"damaging", b"poi_anchors", b"edge_connections"):
        assert marker not in blob


def test_biome_fallback_is_recorded(tmp_path):
    plan = ZonePlan(name="dunes", zone_type="wilderness", prompt="a windswept desert")
    _, _, data = _build(tmp_path, plan)
    assert data["biome"] == "plains"
    assert data["biome_substitution"] == {"requested": "desert", "resolved": "plains"}


@pytest.mark.parametrize("zone_type", ["dungeon", "city"])
def test_room_graph_sidecars_gain_no_wilderness_key(tmp_path, zone_type):
    _, _, data = _build(tmp_path, ZonePlan(name="z", zone_type=zone_type))
    assert not WILD_KEYS & set(data)
