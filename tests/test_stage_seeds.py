"""The rooms seed (world-sockets task 7, P8; Req 4.1, 4.2, 4.4).

A new ``rooms_seed`` on the same ``seed`` keeps the World (its text, the terrain heights
outside the Attachments' Terrain edits, the textures) and lays out other rooms; on a
wilderness it places other Sites on the same ground. Unset, nothing moves (P7 is the
goldens in ``test_layout_engine.py``, ``test_decor_builds.py`` and ``test_site_builds.py``).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from generators import stages
from generators.builder import ZoneBuilder
from generators.zone_spec import ZoneSpec

pytestmark = pytest.mark.slow

SEED = 3
ROOMS = 11


def _build(tmp_path, zone_type: str, rooms_seed=None):
    plan = ZonePlan(name=f"ss_{zone_type}", zone_type=zone_type, decor="none",
                    rooms_seed=rooms_seed)
    spec = plan_to_spec(plan, seed=SEED)
    out = tmp_path / f"r{rooms_seed}"
    return ZoneBuilder(spec).build(output_dir=out, write_glb=False)


def _textures(result) -> dict:
    arc = PfsArchive.from_file(result.eqg_path)
    return {n: arc.get(n) for n in arc.list_files() if n.lower().endswith(".dds")}


def _ground(result) -> np.ndarray:
    return stages.apply_edits(result.world, result.attachments).terrain.heights


def _edited(*results) -> set:
    return {(i, j) for r in results for a in r.attachments for e in a.edits
            for i, j, _ in e.cells}


def _same_world_and_textures(a, b):
    assert a.spec.seed == b.spec.seed == SEED
    assert a.world.to_json() == b.world.to_json()
    ta, tb = _textures(a), _textures(b)
    shared = sorted(set(ta) & set(tb))
    assert shared, "the two builds share material textures"
    assert all(ta[n] == tb[n] for n in shared), [n for n in shared if ta[n] != tb[n]]


def _rooms(result):
    return [(round(r.center_x, 2), round(r.center_y, 2), r.width, r.depth)
            for r in result.spec.rooms]


@pytest.mark.parametrize("zone_type", ["dungeon", "outdoor_dungeon"])
def test_a_rooms_seed_keeps_the_world_and_moves_the_rooms(tmp_path, zone_type):
    base, other = _build(tmp_path, zone_type), _build(tmp_path, zone_type, ROOMS)
    _same_world_and_textures(base, other)
    assert _rooms(base) != _rooms(other)
    assert all(a.seed == ROOMS for a in other.attachments)
    if base.world.terrain is not None:
        ha, hb = _ground(base), _ground(other)
        keep = np.ones(ha.shape, dtype=bool)
        for i, j in _edited(base, other):
            keep[i, j] = False
        assert np.array_equal(ha[keep], hb[keep], equal_nan=True)


def test_a_rooms_seed_moves_the_sites_on_the_same_ground(tmp_path):
    base, other = _build(tmp_path, "wilderness"), _build(tmp_path, "wilderness", ROOMS)
    _same_world_and_textures(base, other)
    assert np.array_equal(_ground(base), _ground(other), equal_nan=True)

    def sites(r):
        att = next(a for a in r.attachments if a.kind == "ground")
        return [(s.kind, round(s.x, 1), round(s.y, 1)) for s in att.sites.sites]
    assert sites(base) and sites(other)
    assert sites(base) != sites(other)


def test_the_sidecar_records_every_stage_seed(tmp_path):
    def seeds(result):
        return json.loads(result.sidecar_path.read_text(encoding="utf-8"))["seeds"]
    assert seeds(_build(tmp_path, "dungeon")) == \
        {"seed": SEED, "rooms_seed": SEED, "decor_seed": SEED}
    other = _build(tmp_path, "dungeon", ROOMS)
    assert seeds(other) == {"seed": SEED, "rooms_seed": ROOMS, "decor_seed": SEED}
    recipe = json.loads(other.handoffs()["ss_dungeon.rooms.json"])["recipe"]
    assert recipe["seed"] == SEED and recipe["rooms_seed"] == ROOMS


def test_the_spec_writes_rooms_seed_only_when_set():
    spec = plan_to_spec(ZonePlan(name="ss_spec", zone_type="dungeon"), seed=SEED)
    assert "rooms_seed" not in spec.to_dict()
    spec.rooms_seed = ROOMS
    again = ZoneSpec.from_dict(spec.to_dict())
    assert again.rooms_seed == ROOMS and again.to_dict() == spec.to_dict()
    with pytest.raises(ValueError, match="rooms_seed"):
        ZonePlan(name="ss_bad", zone_type="dungeon", rooms_seed=-1).validate()
