"""Dungeon verticality task 11 (Requirement 2.1, 3.4; design "Bridges"):
Bridges.

A Bridge is a corridor between two rooms on one Level that crosses a lower
room's footprint (``CorridorSpec.bridge`` names that room). The deck runs
at the corridor's own height, over the lower room's ceiling (a stacked
layout keeps the Slab between them), and the lower room's ceiling is cut
open in a slot under the deck and a margin either side, so the void reads
from both levels; a shaft round the slot runs from the lower ceiling to the
corridor's ceiling, and the deck has low walls (rails) on both edges
(``generators.geometry.bridge_layout``).

Here: the built geometry on a hand spec (flush at both ends, the slot cut
only under the deck, rails over the step-up, nothing of the lower room
changed but its ceiling), the gate passing it and catching a deck with a
hole, the cases ``bridge_layout`` refuses, the JSON, and built bridge
dungeons over a seed sweep passing the gate first try with the room under
every Bridge reachable on foot (a fall off a deck is one-way, so the room
it lands in must be one the walk can leave).

Not checked in the 3D viewer.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import numpy as np
import pytest

import analyzer.traverse as T
from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.traverse import AgentModel, build_walk_surface
from core.ter import TerFile
from generators.builder import connector_record
from generators.geometry import (AUTO_STAIRS, RAIL_MIN, bridge_layout, build_mesh)
from generators.layout import LayoutGenerator
from generators.pipeline import GenerationFailed, generate_validated
from generators.topology.embed import SLAB
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()

HALL_H = 60.0
DECK_Z = 80.0       # a Slab and more over the hall's ceiling
RISE = 4.0          # the deck ramps a little: b's floor is a touch higher


def bridge_spec(*, along_x=True, jog=0.0, hall_depth=200.0, hall_height=HALL_H,
                bridge="c", steps=0):
    """Rooms a and b on the upper Level either side of a lower hall c; one
    corridor a -> b along X (or Y) over c, a Bridge over it."""
    def xy(u, v):
        return (u, v) if along_x else (v, u)

    def dims(w, d):
        return dict(width=w, depth=d) if along_x else dict(width=d, depth=w)

    spec = ZoneSpec(name="bridge", zone_type="dungeon")
    a = RoomSpec("a", *xy(-250.0, 0.0), floor_z=DECK_Z, height=40.0, **dims(100, 100))
    a.role = "entrance"
    a.open_walls = ["E" if along_x else "N"]
    c = RoomSpec("c", *xy(0.0, 0.0), floor_z=0.0, height=hall_height, **dims(300, hall_depth))
    b = RoomSpec("b", *xy(250.0, jog), floor_z=DECK_Z + RISE, height=40.0, **dims(100, 100))
    b.open_walls = ["W" if along_x else "S"]
    spec.rooms = [a, c, b]
    spec.corridors = [CorridorSpec("deck", *xy(-200.0, 0.0), *xy(200.0, jog),
                                   from_z=DECK_Z, to_z=DECK_Z + RISE, width=18.0,
                                   height=15.0, steps=steps, from_room="a",
                                   to_room="b", bridge=bridge)]
    spec.safe_point = (*xy(-250.0, 0.0), DECK_Z + 5)
    return spec


def rooms_of(spec):
    return {r.id: r for r in spec.rooms}


def tris_of(spec):
    """(triangles (n, 3, 3), unit winding normals) of the built mesh."""
    mb = build_mesh(spec)
    V = np.array([(v.x, v.y, v.z) for v in mb.vertices])
    F = np.array([(p.v1, p.v2, p.v3) for p in mb.polygons])
    T3 = V[F]
    n = np.cross(T3[:, 1] - T3[:, 0], T3[:, 2] - T3[:, 0])
    area = np.linalg.norm(n, axis=1)
    return T3, n / np.maximum(area, 1e-12)[:, None], area / 2


def _in(P, rect, eps=1e-6):
    x0, y0, x1, y1 = rect
    return ((P[:, 0] > x0 + eps) & (P[:, 0] < x1 - eps) &
            (P[:, 1] > y0 + eps) & (P[:, 1] < y1 - eps))


@pytest.mark.parametrize("along_x", [True, False])
class TestBridgeGeometry:
    def test_layout(self, along_x):
        spec = bridge_spec(along_x=along_x)
        bl = bridge_layout(spec.corridors[0], rooms_of(spec))
        assert bl is not None
        assert bl.room == "c" and bl.ends == ("wall", "wall")
        assert (bl.s0, bl.s1) == (-150.0, 150.0)       # the hall's walls
        assert bl.margin == pytest.approx(9.0)           # one half-width
        assert min(bl.z0, bl.z1) - bl.ceiling >= SLAB
        assert bl.rail >= RAIL_MIN > AGENT.max_step_up

    def test_ceiling_open_only_under_the_deck(self, along_x):
        spec = bridge_spec(along_x=along_x)
        bl = bridge_layout(spec.corridors[0], rooms_of(spec))
        T3, n, area = tris_of(spec)
        cen = T3.mean(axis=1)
        (hx0, hy0, _), (hx1, hy1, _) = spec.rooms[1].bounds
        ceil = (n[:, 2] < -0.99) & (np.abs(cen[:, 2] - HALL_H) < 1e-6)
        ceil &= _in(cen, (hx0, hy0, hx1, hy1), eps=-1e-6)
        sx0, sy0, sx1, sy1 = bl.slot
        assert not _in(cen[ceil], bl.slot).any(), "ceiling left over the slot"
        assert area[ceil].sum() == pytest.approx(
            (hx1 - hx0) * (hy1 - hy0) - (sx1 - sx0) * (sy1 - sy0))
        # Nothing else of the hall changed: every face of the same spec
        # without the Bridge is still there, but the hall's ceiling and the
        # corridor over the slot.
        plain = dataclasses.replace(spec, corridors=[
            dataclasses.replace(spec.corridors[0], bridge="")])
        T0, n0, _ = tris_of(plain)
        have = {tuple(np.round(t, 6).ravel()) for t in T3}
        for t, nn in zip(T0, n0):
            if tuple(np.round(t, 6).ravel()) in have:
                continue
            c = t.mean(axis=0)
            hall_ceiling = nn[2] < -0.99 and abs(c[2] - HALL_H) < 1e-6
            over_slot = (_in(c[None], bl.slot, eps=-1e-6)[0] and c[2] > HALL_H)
            assert hall_ceiling or over_slot, f"face {t.tolist()} changed"

    def test_deck_flush_rails_and_open_margins(self, along_x):
        spec = bridge_spec(along_x=along_x)
        bl = bridge_layout(spec.corridors[0], rooms_of(spec))
        T3, n, _ = tris_of(spec)
        ia, ic = (0, 1) if along_x else (1, 0)
        up = n[:, 2] > 0.5

        def floor_z(s, v):
            """Up-facing floor heights over the point (s along, v across)."""
            P = np.zeros(2)
            P[ia], P[ic] = s, v
            out = []
            for t in T3[up]:
                (x0, y0), (x1, y1), (x2, y2) = t[:, :2]
                d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
                l1 = ((y1 - y2) * (P[0] - x2) + (x2 - x1) * (P[1] - y2)) / d
                l2 = ((y2 - y0) * (P[0] - x2) + (x0 - x2) * (P[1] - y2)) / d
                l3 = 1 - l1 - l2
                if min(l1, l2, l3) >= -1e-9:
                    out.append(l1 * t[0, 2] + l2 * t[1, 2] + l3 * t[2, 2])
            return sorted(set(np.round(out, 6)))

        c = bl.cross
        for s in (bl.s0, bl.s1):
            for ds in (-0.5, 0.5):
                # Over the slot the deck is the only floor above the hall's.
                zs = [z for z in floor_z(s + ds, c) if z > 1.0]
                assert zs == [pytest.approx(bl.z_at(s + ds), abs=1e-6)], (s, ds, zs)
        # The margins: no floor between the deck and the shaft walls but the
        # hall's own, far below.
        for v in (c - bl.hw - bl.margin / 2, c + bl.hw + bl.margin / 2):
            assert floor_z((bl.s0 + bl.s1) / 2, v) == [0.0]
        # Rails: a wall on each deck edge from the deck to the rail's top.
        side = np.abs(n[:, 2]) < 1e-6
        for v in (c - bl.hw, c + bl.hw):
            on = side & np.all(np.abs(T3[:, :, ic] - v) < 1e-6, axis=1)
            on &= np.all((T3[:, :, ia] >= bl.s0 - 1e-6) & (T3[:, :, ia] <= bl.s1 + 1e-6), axis=1)
            top = T3[on][:, :, 2].max()
            assert top == pytest.approx(max(bl.z0, bl.z1) + bl.rail)

    def test_gate_passes_the_deck(self, along_x):
        spec = bridge_spec(along_x=along_x)
        rooms = rooms_of(spec)
        cor = spec.corridors[0]
        surf = build_walk_surface(build_mesh(spec).to_ter("bridge"), AGENT)
        assert T.bridged_rooms(cor, {"c"}, rooms, AGENT) == {"c"}
        chk = T.check_connector(surf, cor, rooms, AGENT, bridged={"c"})
        assert chk.kind == "bridge" and chk.ok, chk.reason
        assert chk.min_headroom >= AGENT.player_height
        (res,) = T.corridor_continuity(surf, spec, AGENT)
        assert res.connected, res.reason


def test_gate_catches_a_hole_in_the_deck():
    """The built deck with a stretch of its floor taken out over the hall is
    a "gap in bridge deck", in the connector walk and the gate."""
    spec = bridge_spec()
    rooms = rooms_of(spec)
    mb = build_mesh(spec)
    ter = mb.to_ter("bridge")
    V = np.array([(v.x, v.y, v.z) for v in ter.vertices])
    keep = []
    for p in ter.polygons:
        t = V[[p.v1, p.v2, p.v3]]
        nz = np.cross(t[1] - t[0], t[2] - t[0])[2]
        c = t.mean(axis=0)
        if nz > 0 and -150.0 < c[0] < 0.0 and c[2] > HALL_H:
            continue                     # the deck's first half
        keep.append(p)
    holed = TerFile(name="holed")
    holed.vertices, holed.polygons, holed.materials = ter.vertices, keep, ter.materials
    surf = build_walk_surface(holed, AGENT)
    chk = T.check_connector(surf, spec.corridors[0], rooms, AGENT, bridged={"c"})
    assert not chk.ok and chk.reason.startswith("gap in bridge deck"), chk.reason
    (res,) = T.corridor_continuity(surf, spec, AGENT)
    assert not res.connected and res.reason.startswith("gap in bridge deck"), res.reason


@pytest.mark.parametrize("kw, why", [
    (dict(bridge=""), "not a bridge"),
    (dict(bridge="a"), "its own room"),
    (dict(steps=AUTO_STAIRS), "a stair"),
    (dict(jog=10.0), "turns over the hall"),
    (dict(hall_depth=30.0), "slot doesn't fit"),
    (dict(hall_height=DECK_Z - SLAB + 1.0), "under the Slab"),
])
def test_bridge_layout_refuses(kw, why):
    spec = bridge_spec(**kw)
    assert bridge_layout(spec.corridors[0], rooms_of(spec)) is None, why


def test_connector_record_says_bridge_and_names_the_lower_room():
    (cid, rec), = connector_record(bridge_spec()).items()
    assert rec["kind"] == "bridge" and rec["over"] == "c", (cid, rec)
    (cid, rec), = connector_record(bridge_spec(bridge="")).items()
    assert rec["kind"] != "bridge" and "over" not in rec, (cid, rec)


def test_json_carries_bridge_only_when_set():
    spec = bridge_spec()
    d = spec.to_dict()
    assert d["corridors"][0]["bridge"] == "c"
    back = ZoneSpec.from_dict(json.loads(json.dumps(d)))
    assert back.corridors[0].bridge == "c"
    plain = bridge_spec(bridge="").to_dict()
    assert "bridge" not in plain["corridors"][0]


# ---------------------------------------------------------------------------
# Built bridge dungeons
# ---------------------------------------------------------------------------

#: (verticality, room count, seed): classic_eq builds the bridge_hall rule
#: grows on; about half of this sweep grows at least one Bridge.
SWEEP = [(v, n, s) for v in ("moderate", "dramatic") for n in (8, 12, 16) for s in range(6)]


def _plan(n, verticality, rule_set="classic_eq", theme=""):
    return ZonePlan(name="br", zone_type="dungeon", room_count=n, layout="graph",
                    rule_set=rule_set, dungeon_theme=theme,
                    verticality=verticality).validate()


def _bridges(spec):
    return [c.bridge for c in spec.corridors if c.bridge]


@pytest.mark.gate
@pytest.mark.slow
@pytest.mark.parametrize("v, n, seed", SWEEP, ids=[f"{v}-{n}-{s}" for v, n, s in SWEEP])
def test_bridge_dungeons_pass_the_gate_first_try(tmp_path, v, n, seed):
    """One case of the sweep (a test each, so the sweep spreads over the workers): a
    plan that grows a Bridge passes the gate on its pinned seed, every deck connected."""
    plan = _plan(n, v)
    want = _bridges(plan_to_spec(plan, seed=seed))
    if not want:
        return
    try:
        vb = generate_validated(lambda s: plan_to_spec(plan, seed=s),
                                zone_type="dungeon", zone_id=f"br{n}_{seed}_{v}",
                                seed=seed, output_dir=tmp_path, write_glb=False,
                                max_attempts=1, failure_log=None)
    except GenerationFailed as e:
        pytest.fail(f"{(v, n, seed)}: {str(e)[:300]}")
    assert _bridges(vb.spec) == want
    # A fall off a deck lands in the room under it: that room must be
    # one the walk reaches on foot from the spawn.
    reach = {r.room_id: r.reachable for r in vb.report.rooms}
    assert all(reach[h] for h in want), (v, n, seed, want)
    res = {r.corridor_id: r for r in vb.report.corridors}
    for c in vb.spec.corridors:
        if c.bridge:
            assert res[c.id].connected, (c.id, res[c.id].reason)


@pytest.mark.slow
def test_a_third_of_the_sweep_grows_a_bridge():
    """The sweep above reaches Bridges: at least a third of its plans grow one (planning
    only; the builds are the per-case tests')."""
    grown = [(v, n, s) for v, n, s in SWEEP if _bridges(plan_to_spec(_plan(n, v), seed=s))]
    print(f"\nbridges grown in {len(grown)}/{len(SWEEP)} builds")
    assert len(grown) >= len(SWEEP) // 3, grown


@pytest.mark.parametrize("n, seed", [(12, s) for s in range(6)])
def test_built_bridges_are_recorded_as_bridges(n, seed):
    spec = plan_to_spec(_plan(n, "dramatic"), seed=seed)
    rec = connector_record(spec)
    for c in spec.corridors:
        assert (rec[c.id]["kind"] == "bridge") == bool(c.bridge), c.id
        assert rec[c.id].get("over", "") == c.bridge, c.id


def _hash(spec) -> str:
    return hashlib.sha256(json.dumps(spec.to_dict(), sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize("rule_set, n, seed", [
    ("classic_eq", 12, 0), ("classic_eq", 16, 3), ("warren", 12, 1), ("warren", 16, 4),
])
def test_marking_bridges_moves_nothing_else(monkeypatch, rule_set, n, seed):
    """Job B's Bridge pass changes only the corridors it bridges (their
    ``bridge`` and, when it straightens one, its door points); a stacked
    build without a Bridge is the same with the pass or without it."""
    plan = _plan(n, "moderate", rule_set)
    with_pass = plan_to_spec(plan, seed=seed)
    monkeypatch.setattr(LayoutGenerator, "_mark_bridges", lambda *a, **k: None)
    without = plan_to_spec(plan, seed=seed)
    if not _bridges(with_pass):
        assert _hash(with_pass) == _hash(without)
        return
    d1, d0 = with_pass.to_dict(), without.to_dict()
    for c1, c0 in zip(d1.pop("corridors"), d0.pop("corridors")):
        if c1.get("bridge"):
            for k in ("from_x", "from_y", "to_x", "to_y", "bridge"):
                c1.pop(k, None)
                c0.pop(k, None)
        assert c1 == c0
    assert d1 == d0


def test_straightening_keeps_off_a_door_already_on_the_wall():
    """Cave graph moderate 30 rooms, seed 432395022, Winding 2 (winding-control task 4):
    straightening room_6-room_2 into a Bridge moved its door onto room_2's west wall 14 u
    from the stair to room_8's door, both 18 u wide; the overlapping openings left an open
    seam. ``_straight_cor`` judged the new route only against corridors leaving neither
    room. It now judges every corridor and keeps two doors on one wall a width and a pier
    (``U_DOOR_MARGIN``) apart."""
    import itertools

    plan = ZonePlan.from_controls({"zone_type": "dungeon", "room_count": 30, "verticality": "moderate",
                                   "layout": "graph", "dungeon_theme": "cave", "winding": 2}, [])
    plan.name = "doors"
    spec = plan_to_spec(plan, seed=432395022, warnings=[])
    room_2 = next(r for r in spec.rooms if r.id == "room_2")
    walls = {LayoutGenerator._door_on_wall(c, room_2)[0] for c in spec.corridors
             if "room_2" in (c.from_room, c.to_room) and LayoutGenerator._door_on_wall(c, room_2)}
    assert "W" in walls, "the layout moved: re-pin"
    for r in spec.rooms:
        cs = [c for c in spec.corridors if r.id in (c.from_room, c.to_room)]
        for a, b in itertools.combinations(cs, 2):
            da, db = LayoutGenerator._door_on_wall(a, r), LayoutGenerator._door_on_wall(b, r)
            if da and db and da[0] == db[0] and abs(da[1] - db[1]) > 1e-6:
                assert abs(da[1] - db[1]) >= (a.width + b.width) / 2, (r.id, a.id, b.id)


def test_a_slot_keeps_off_a_door_on_the_bridged_rooms_wall():
    """Cave graph moderate 27 rooms, Winding 2 (winding-control task 10): at seed 2071938654
    corr_8 bridged room_5 with a slot reaching its west wall, where corr_12's straight door
    runs 2 u into the room; that piece's side wall stood in the slot's Throat ("wall across
    throat"). A jittered build now makes no Bridge whose slot meets a door's in-room piece.
    Re-pinned by random placement task 1 (the offsets salt with the build's seed): at seed
    782009009 the rule refuses two Bridges, and corr_24's slot in room_22 comes within 2.5 u
    of the north wall, where corr_2 has its door. Re-pinned by random placement task 10
    (caves at any bearing; 782009009 now makes no Bridge): at seed 1001 corr_19's slot in
    room_21 comes within 2.5 u of the west wall, where corr_8 has its door. Re-pinned by random
    placement task 11 (room sizes vary): at seed 1013 corr_21's slot in room_17 reaches the west
    wall, where corr_17 has its door."""
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "room_count": 27, "verticality": "moderate",
                                   "layout": "graph", "dungeon_theme": "cave", "winding": 2}, [])
    plan.name = "slots"
    spec = plan_to_spec(plan, seed=1013, warnings=[])
    rooms = {r.id: r for r in spec.rooms}
    room_17 = rooms["room_17"]
    assert any((LayoutGenerator._door_on_wall(c, room_17) or ("",))[0] == "W" for c in spec.corridors
               if c.id == "corr_17"), "the layout moved: re-pin"
    assert any(c.id == "corr_21" and c.bridge == "room_17" for c in spec.corridors), "the layout moved: re-pin"
    checked = 0
    for cor in spec.corridors:
        bl = bridge_layout(cor, rooms) if cor.bridge else None
        if bl is None:
            continue
        hall = rooms[cor.bridge]
        (x0, y0, _), (x1, y1, _) = hall.bounds
        s = bl.slot
        for other in spec.corridors:
            at = LayoutGenerator._door_on_wall(other, hall)
            if other is cor or at is None:
                continue
            wall, c = at
            hw = other.width / 2
            p = {"W": (x0, c - hw, x0 + 2, c + hw), "E": (x1 - 2, c - hw, x1, c + hw),
                 "S": (c - hw, y0, c + hw, y0 + 2), "N": (c - hw, y1 - 2, c + hw, y1)}[wall]
            checked += 1
            assert (min(s[2], p[2]) - max(s[0], p[0]) <= 1e-6
                    or min(s[3], p[3]) - max(s[1], p[1]) <= 1e-6), (cor.id, other.id, hall.id)
    assert checked
