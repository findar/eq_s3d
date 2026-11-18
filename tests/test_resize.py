"""
tests/test_resize.py
--------------------
The resize ops (zone-generator-edits Req 2.7, task 7): ``generators.resize.resize_room`` and
``apply_edits``' resize rows.

On task 2's four specs, every room and op: the triangles of every room and corridor outside the
Affected_Set are unchanged (umbrella 19.2), compared element by element (the polygons each
``MeshBuilder.add_room``/``add_corridor`` call adds, sorted, by material name). A clamped resize
notes the size asked for and applied (19.4); one nothing fits is rejected and the input is
unchanged. And a resized build of each zone type resize takes passes the pipeline's gate.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators import geometry as geo
from generators.builder import ZoneBuilder, assign_texel_densities
from generators.decor.stock import eq_path_from_env
from generators.edits import FULL, apply_edits
from generators.resize import fit, redress, resize_room
from generators.zone_spec import ZoneSpec

#: Task 2's specs: label -> (ZonePlan fields, seed).
PLANS = {
    "graph16_s2": (dict(zone_type="dungeon", room_count=16, layout="graph"), 2),
    "graph12_dramatic_s7": (dict(zone_type="dungeon", room_count=12, layout="graph",
                                 verticality="dramatic"), 7),
    "tomb_s4": (dict(zone_type="dungeon", dungeon_theme="tomb"), 4),
    "classic8_s3": (dict(zone_type="dungeon", room_count=8, layout="classic"), 3),
    "city_s5": (dict(zone_type="city"), 5),
}

#: Task 2's factors, as decision 7's ``by``: x1.25, x0.75, x1.3, x0.7.
OPS = {"widen_room": 0.25, "narrow_room": 0.25, "taller_room": 0.3, "lower_room": 0.3}


@functools.lru_cache(maxsize=None)
def _doc(label: str) -> dict:
    """The saved spec of ``label`` (shared: every test checks it is left unchanged)."""
    fields, seed = PLANS[label]
    spec = plan_to_spec(ZonePlan(name=f"rs_{label}", **fields).validate(), seed=seed)
    return json.loads(json.dumps({**spec.to_dict(), "decor_layers": []}))


def _spec(doc: dict) -> ZoneSpec:
    return ZoneSpec.from_dict(json.loads(json.dumps({k: v for k, v in doc.items()
                                                     if k != "decor_layers"})))


def _parts(doc: dict) -> dict:
    """The builder's geometry stage, split per element: ``R:<id>`` / ``C:<id>`` -> a hash of
    its sorted triangles (positions, UVs, flags, material name)."""
    spec = _spec(doc)
    spans = []
    add_room, add_corridor = geo.MeshBuilder.add_room, geo.MeshBuilder.add_corridor

    def room(self, r, *a, **k):
        s = len(self.polygons)
        add_room(self, r, *a, **k)
        spans.append(("R:" + r.id, s, len(self.polygons)))

    def corridor(self, c, *a, **k):
        s = len(self.polygons)
        add_corridor(self, c, *a, **k)
        spans.append(("C:" + c.id, s, len(self.polygons)))

    geo.MeshBuilder.add_room, geo.MeshBuilder.add_corridor = room, corridor
    try:
        b = ZoneBuilder(spec)
        assign_texel_densities(spec)
        ter, backend, _ = b._build_geometry(spec.name.lower(), 2)
    finally:
        geo.MeshBuilder.add_room, geo.MeshBuilder.add_corridor = add_room, add_corridor
    assert backend == "box"
    out = {}
    for eid, s, e in spans:
        tris = []
        for p in ter.polygons[s:e]:
            vs = tuple(sorted((round(v.x, 3), round(v.y, 3), round(v.z, 3), round(v.u, 3),
                               round(v.v, 3))
                              for v in (ter.vertices[p.v1], ter.vertices[p.v2], ter.vertices[p.v3])))
            tris.append((ter.materials[p.material].name, p.flags, vs))
        out[eid] = hashlib.sha1(repr(sorted(tris)).encode()).hexdigest()
    return out


@pytest.mark.slow
@pytest.mark.parametrize("label", ["graph16_s2", "graph12_dramatic_s7", "tomb_s4", "classic8_s3"])
def test_nothing_outside_the_affected_set_moves(label):
    doc = _doc(label)
    base = _parts(doc)
    refused = []
    for room in [r["id"] for r in doc["rooms"]]:
        for op, by in OPS.items():
            res = resize_room(doc, room, op, by)
            if not res.applied:
                refused.append((room, op))
                continue
            keep = {"R:" + r for r in res.affected["rooms"]} | \
                   {"C:" + c for c in res.affected["corridors"]}
            assert "R:" + room in keep
            parts = _parts(res.doc)
            moved = sorted(k for k in base if parts[k] != base[k] and k not in keep)
            assert not moved, (room, op, res.notes, moved)
    # Task 2 measured two refusals, both widening across corr_3's ramp.
    want = [("room_1", "widen_room"), ("room_4", "widen_room")] \
        if label == "graph12_dramatic_s7" else []
    assert refused == want


def test_re_dressing_an_unchanged_spec_changes_nothing():
    # Without the saved Transition look a frame's materials move (graph16 seed 2, corr_13).
    doc = _doc("graph16_s2")
    spec = _spec(doc)
    redress(spec)
    assert {**json.loads(json.dumps(spec.to_dict())), "decor_layers": []} == doc


def test_a_clamped_resize_notes_the_size_asked_and_applied():
    doc = _doc("graph16_s2")
    before = copy.deepcopy(doc)
    res = apply_edits(doc, [{"op": "widen_room", "target": "room_6", "by": 0.25}], 7, 1)
    assert doc == before
    assert res.how == FULL and not res.rejected
    assert res.notes == ["widened room_6 by 4% of the 25% asked; "
                         "any more and corr_5 would overlap room_6"]
    assert res.changed == ["width", "depth"]
    room = next(r for r in res.doc["rooms"] if r["id"] == "room_6")
    old = next(r for r in doc["rooms"] if r["id"] == "room_6")
    assert 1.0 < room["width"] / old["width"] < 1.25
    assert room["floor_z"] == old["floor_z"] and room["height"] == old["height"]
    assert res.affected_rooms[0] == "room_6" and "room_12" in res.affected_rooms


def test_a_full_resize_scales_about_the_centre():
    doc = _doc("graph16_s2")
    res = apply_edits(doc, [{"op": "taller_room", "target": "room_0", "by": 0.3}], 7, 1)
    assert res.notes == ["heightened room_0 by 30%"] and res.changed == ["height"]
    room = next(r for r in res.doc["rooms"] if r["id"] == "room_0")
    old = next(r for r in doc["rooms"] if r["id"] == "room_0")
    assert room["height"] == pytest.approx(old["height"] * 1.3)
    assert (room["center_x"], room["center_y"], room["floor_z"], room["width"]) == \
           (old["center_x"], old["center_y"], old["floor_z"], old["width"])


def test_a_resize_nothing_fits_is_rejected():
    doc = _doc("graph12_dramatic_s7")
    before = copy.deepcopy(doc)
    res = apply_edits(doc, [{"op": "widen_room", "target": "room_1"},
                            {"op": "set_decor_level", "level": "sparse"}], 7, 1)
    assert doc == before
    assert [r["op"]["op"] for r in res.rejected] == ["widen_room"]
    assert res.notes[0] == ("widen_room: can't widen room_1 at all (25% asked): "
                            "corr_3's ramp would be too steep (grade 0.80)")
    assert res.changed == ["decor"]                 # the rest still apply
    alone = resize_room(doc, "room_1", "widen_room", 0.25)
    assert not alone.applied and alone.doc == before and alone.affected == {"rooms": [],
                                                                            "corridors": []}


def test_lower_stops_where_the_room_is_no_taller_than_its_corridors():
    doc = _doc("graph16_s2")
    spec, got, why = fit(doc, "room_1", "lower_room", 0.7)
    assert spec is not None and 0.7 < got < 0.72 and why == "the room would be lower than corr_8"


def test_rooms_under_a_hill_are_not_resized():
    doc = {**_doc("graph16_s2"), "zone_type": "outdoor_dungeon"}
    res = apply_edits(doc, [{"op": "narrow_room", "target": "room_1"}], 7, 1)
    assert res.how is None and res.notes == ["narrow_room: rooms under a hill can't be resized yet"]


@pytest.mark.slow
@pytest.mark.parametrize("label, room, op", [
    ("graph16_s2", "room_3", "widen_room"),
    ("graph16_s2", "room_6", "lower_room"),
    ("graph12_dramatic_s7", "room_2", "taller_room"),
    ("tomb_s4", "room_3", "lower_room"),
    ("classic8_s3", "room_3", "narrow_room"),
    ("city_s5", "room_1", "widen_room"),
])
def test_a_resized_build_passes_the_gate(tmp_path, label, room, op):
    if eq_path_from_env() is None:
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    from generators.pipeline import generate_validated
    doc = _doc(label)
    res = apply_edits(doc, [{"op": op, "target": room, "by": OPS[op]}], 7, 1)
    assert res.how == FULL and not res.rejected, res.notes
    text = json.dumps({k: v for k, v in res.doc.items() if k != "decor_layers"})
    vb = generate_validated(lambda s: ZoneSpec.from_dict(json.loads(text)),
                            zone_type=doc["zone_type"], zone_id=f"rs_{label}", seed=doc["seed"],
                            output_dir=tmp_path, write_glb=False, max_attempts=1,
                            failure_log=None)
    assert vb.attempts == 1
