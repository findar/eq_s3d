"""
tests/test_layout_levels.py
---------------------------
Dungeon verticality task 5 (Requirements 4.3-4.5; design "Stacking",
"Staircases"): the shared layout steps (Job B) in 3D.

With stacking on (``GraphEngine(stacking=True)``) and rooms on more than one
Level, Job B judges rooms and corridors through ``embed.may_overlap_in_plan``
and the Slab: separation leaves stacked pairs over each other, floors sit at
Level x level height (plus a variation inside a band), an edge across Levels
is a planned stair (``steps = AUTO_STAIRS``, a Switchback's stairwell kept
clear), crossing splits and conflict drops let a corridor pass over or under
a room with the Slab between, and the gate's room-face test picks a room's
own floor.

V4  no room pair overlaps in plan unless on different Levels with the Slab;
    no corridor (stairwell included) passes through a room without the
    Slab's clearance.
V5  every edge across Levels is a stair, every other edge a ramp or flat;
    the built graph is connected; the gate finds every room on stacked
    builds (ZoneBuilder, ``analyzer.traverse.validate``).
V6  classic and step 6 graph builds unchanged: the goldens live in
    ``tests/test_layout_engine.py`` and ``tests/test_topology_levels.py``;
    here, a graph build with one Level is the same with stacking on or off.

The vertical rule set is task 4's test set (``tests/test_topology_levels.py``
``VERT``) written to ``tmp_path``; the shipped sets' vertical rules are task
6's.
"""

from __future__ import annotations

import pytest

from analyzer.traverse import (AgentModel, _faces_in_room, build_walk_surface,
                               validate)
from generators.builder import ZoneBuilder
from generators.geometry import AUTO_STAIRS, MeshBuilder, build_mesh, stair_layout
from generators.layout import LEVEL_VARIATION, LayoutGenerator
from generators.layout_engine import GraphEngine
from generators.routing import corridor_route, plan_u_route
from generators.topology import embed
from generators.topology.ruleset import load_rule_set
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

from tests.test_topology_levels import VERT

SWEEP = [(n, seed) for n in (8, 12, 18) for seed in range(5)]


@pytest.fixture(scope="module")
def vert(tmp_path_factory):
    p = tmp_path_factory.mktemp("rules") / "vert.toml"
    p.write_text(VERT, encoding="utf-8")
    return load_rule_set(p)


def _build(rs, n, seed, stacking=True, race=""):
    gen = LayoutGenerator("dungeon", seed=seed, engine=GraphEngine(rs, stacking=stacking))
    spec = gen.generate(f"lv_{n}_{seed}", room_count=n, dungeon_race=race)
    spec.layout = gen.layout_record          # as ai.expand.plan_to_spec does
    return gen, spec


@pytest.fixture(scope="module")
def stacked(vert):
    """(gen, spec, levels by room id) over the sweep, no race and ogre."""
    out = []
    for race in ("", "ogre"):
        for n, seed in SWEEP:
            gen, spec = _build(vert, n, seed, race=race)
            out.append((gen, spec, gen.layout_record["levels"]))
    return out


def _overlap(a, b) -> bool:
    return (min(a[2], b[2]) - max(a[0], b[0]) > 1e-6
            and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6)


def _footprint(r: RoomSpec):
    return (r.center_x - r.width / 2, r.center_y - r.depth / 2,
            r.center_x + r.width / 2, r.center_y + r.depth / 2)


def _corridor_pieces(cor: CorridorSpec, rooms):
    """A corridor's floor as built: (rect, lowest floor, top of the tube,
    leg index or None) for each leg, bend square and stairwell."""
    route = corridor_route(cor, rooms)
    wps = list(route.waypoints)
    zs, _ = MeshBuilder._waypoint_zs(wps, None if route.carry < 0 else route.carry,
                                     cor.from_z, cor.to_z)
    hw, h = cor.width / 2, cor.height
    out = []
    for k in range(len(wps) - 1):
        (x0, y0), (x1, y1) = wps[k], wps[k + 1]
        out.append(((min(x0, x1) - hw, min(y0, y1) - hw, max(x0, x1) + hw, max(y0, y1) + hw),
                    min(zs[k], zs[k + 1]), max(zs[k], zs[k + 1]) + h, k))
    for w in range(1, len(wps) - 1):
        cx, cy = wps[w]
        out.append(((cx - hw, cy - hw, cx + hw, cy + hw), zs[w], zs[w] + h, None))
    lay = stair_layout(cor, rooms)
    if lay is not None and lay.stairwell is not None:
        out.append((lay.stairwell, min(cor.from_z, cor.to_z),
                    max(cor.from_z, cor.to_z) + h, None))
    return out, len(wps) - 1


# ---------------------------------------------------------------------------
# V4: stacked pairs only with the Slab; no corridor through a room
# ---------------------------------------------------------------------------

def test_v4_rooms_overlap_only_stacked_with_the_slab(stacked):
    pairs = 0
    for gen, spec, levels in stacked:
        rooms = spec.rooms
        st = {r.id: embed.Storey(levels[r.id], r.floor_z, r.height) for r in rooms}
        for k, a in enumerate(rooms):
            for b in rooms[k + 1:]:
                if _overlap(_footprint(a), _footprint(b)):
                    pairs += 1
                    assert embed.may_overlap_in_plan(st[a.id], st[b.id]), (
                        spec.name, a.id, b.id)
    assert pairs > 20, pairs      # the sweep does stack


def test_v4_no_corridor_through_a_room(stacked):
    """Every leg, bend and stairwell of every corridor is clear of every room
    it overlaps in plan by the Slab (over its ceiling or under its floor);
    only a corridor's end legs enter its own rooms, through their doors."""
    for gen, spec, levels in stacked:
        rooms = {r.id: r for r in spec.rooms}
        for cor in spec.corridors:
            pieces, n = _corridor_pieces(cor, rooms)
            for r in spec.rooms:
                fp = _footprint(r)
                for rect, zlo, zhi, leg in pieces:
                    if r.id == cor.from_room and leg == 0:
                        continue
                    if r.id == cor.to_room and leg == n - 1:
                        continue
                    if r.id in (cor.from_room, cor.to_room) and cor.steps != AUTO_STAIRS:
                        continue    # step 6's rule for a corridor within a Level
                    if not _overlap(rect, fp):
                        continue
                    assert (zlo >= r.floor_z + r.height + embed.SLAB - 1e-6
                            or zhi + embed.SLAB <= r.floor_z + 1e-6), (
                        spec.name, cor.id, r.id)


def test_floors_at_their_levels(stacked):
    for gen, spec, levels in stacked:
        lh = gen.layout_record["level_height"]
        for r in spec.rooms:
            assert abs(r.floor_z - levels[r.id] * lh) <= LEVEL_VARIATION / 2 + 1e-6, (
                spec.name, r.id)
        assert gen.layout_record["relations_broken"] == 0, spec.name


# ---------------------------------------------------------------------------
# V5: stairs across Levels; connected; the gate finds every room
# ---------------------------------------------------------------------------

def _connected(spec) -> bool:
    parent = {r.id: r.id for r in spec.rooms}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for c in spec.corridors:
        parent[find(c.from_room)] = find(c.to_room)
    return len({find(r.id) for r in spec.rooms}) == 1


def test_v5_edges_across_levels_are_stairs(stacked):
    stairs = 0
    for gen, spec, levels in stacked:
        assert _connected(spec), spec.name
        for c in spec.corridors:
            across = levels[c.from_room] != levels[c.to_room]
            assert (c.steps == AUTO_STAIRS) == across, (spec.name, c.id)
            stairs += across
            if across:
                rooms = {r.id: r for r in spec.rooms}
                lay = stair_layout(c, rooms)
                assert lay is not None and not lay.cramped, (spec.name, c.id)
    assert stairs > 50, stairs


GATE_BUILDS = [(8, 1), (12, 2), (18, 3)]


@pytest.mark.parametrize("n,seed", GATE_BUILDS)
def test_v5_gate_finds_every_room_on_stacked_builds(vert, tmp_path, n, seed):
    gen, spec = _build(vert, n, seed)
    assert len(set(gen.layout_record["levels"].values())) > 1
    assert any(c.steps == AUTO_STAIRS for c in spec.corridors)
    res = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    rep = validate(res.eqg_path, spec=spec, check_corridors=True)
    assert rep.passed, [(r.room_id, r.reason) for r in rep.rooms if not r.reachable]
    assert rep.corridors_passed, (
        [(c.corridor_id, c.reason) for c in rep.corridors if not c.connected],
        rep.conflicts)


def test_faces_in_room_stays_on_its_storey():
    """Two rooms built one over the other, and a third room between them with
    no floor of its own: z-bounded, the room-face test finds nothing for it
    rather than the storey above or below (step 6's terrain fallback took
    every face in its footprint). The two built rooms find their own floor."""
    spec = ZoneSpec(name="storeys", zone_type="dungeon")
    low = RoomSpec("low", 0.0, 0.0, floor_z=0.0, width=200, depth=200, height=80)
    high = RoomSpec("high", 40.0, 0.0, floor_z=120.0, width=200, depth=200, height=80)
    spec.rooms = [low, high]
    surf = build_walk_surface(build_mesh(spec).to_ter(spec.name), AgentModel())
    between = RoomSpec("between", 20.0, 0.0, floor_z=98.0, width=100, depth=100, height=4)
    rooms = [low, high, between]
    for r in (low, high):
        faces = _faces_in_room(surf, r, rooms)
        assert len(faces)
        z = surf.centroids[faces][:, 2]
        assert z.min() >= r.floor_z - 8 and z.max() <= r.floor_z + r.height + 4
    assert len(_faces_in_room(surf, between)) > 0           # the old fallback
    assert len(_faces_in_room(surf, between, rooms)) == 0


def test_u_route_shape():
    r = plan_u_route((0.0, 98.0), (300.0, 120.0), "N", 40.0)
    assert r.kind == "u" and r.carry == 1 and r.axes == (False, True, False)
    assert r.waypoints == ((0.0, 98.0), (0.0, 160.0), (300.0, 160.0), (300.0, 120.0))
    w = plan_u_route((98.0, 0.0), (90.0, 300.0), "W", 40.0)
    assert w.waypoints[1] == (50.0, 0.0) and w.axes == (True, False, True)


# ---------------------------------------------------------------------------
# V6: one Level is step 6
# ---------------------------------------------------------------------------

def test_v6_one_level_stacking_on_is_step6(tmp_path):
    flat = VERT
    for rel in ("above", "below", "level"):
        flat = flat.replace(f', rel = "{rel}"', "")
    p = tmp_path / "vert.toml"
    p.write_text(flat, encoding="utf-8")
    rs = load_rule_set(p)
    for seed in range(3):
        _, on = _build(rs, 12, seed, stacking=True)
        _, off = _build(rs, 12, seed, stacking=False)
        on_d, off_d = on.to_dict(), off.to_dict()
        for d in (on_d, off_d):
            d.pop("name"), d.pop("layout")     # the record names its Levels
        assert on_d == off_d
        assert all("side" not in c for c in off_d["corridors"])
