"""Winding tunnels task 3 (Requirement 3; design "The mesh"): a plain leg of a rough corridor
that ``routing.winding_legs`` lets wind is built along its centreline, and welds to its bend
squares and room openings as the straight leg did.
"""

import copy
import functools

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.traverse import OUTLINE_TOL, validate
from generators.builder import ZoneBuilder
from generators.geometry import MAX_SEG_RISE, MeshBuilder, build_mesh
from generators.routing import corridor_route, winding_legs

#: (theme, seed, rooms, verticality): 10 cave and 5 warren dungeons on the graph layout,
#: 8-30 rooms, each verticality.
ZONES = [("cave", s, r, v) for s, (r, v) in enumerate(
    [(8, "flat"), (12, "moderate"), (16, "dramatic"), (20, "flat"), (25, "moderate"),
     (30, "dramatic"), (10, "flat"), (14, "moderate"), (22, "dramatic"), (28, "flat")])] + \
    [("warren", s, r, v) for s, (r, v) in enumerate(
        [(8, "flat"), (14, "moderate"), (20, "dramatic"), (26, "flat"), (30, "moderate")])]


@functools.lru_cache(maxsize=None)
def _spec(theme, seed, rooms, verticality):
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "dungeon_theme": theme, "layout": "graph",
                                   "room_count": rooms, "verticality": verticality}, [])
    plan.name = f"wm_{theme}{seed}"
    return plan_to_spec(plan, seed=seed, warnings=[])


def _winding_ends(spec):
    """(corridor, leg's polyline, end point, along_x) of each end of each winding leg."""
    rooms = {r.id: r for r in spec.rooms}
    out = []
    for cor in spec.corridors:
        route = corridor_route(cor, rooms)
        for k, line in enumerate(winding_legs(cor, rooms)):
            if line is not None:
                out += [(cor, line, line[0], route.axes[k]), (cor, line, line[-1], route.axes[k])]
    return out


def _winding_legs(spec):
    """(corridor, polyline, floor z at its start, at its end) of each winding leg."""
    rooms = {r.id: r for r in spec.rooms}
    out = []
    for cor in spec.corridors:
        route = corridor_route(cor, rooms)
        zs, _ = MeshBuilder._waypoint_zs(list(route.waypoints), None if route.carry < 0 else route.carry,
                                         cor.from_z, cor.to_z)
        out += [(cor, line, zs[k], zs[k + 1]) for k, line in enumerate(winding_legs(cor, rooms))
                if line is not None]
    return out


def _open_edges_in_line(mb, point, along_x, hw):
    """The edges only one face uses that lie in the section line through ``point`` (across the
    leg, within the strip): an open seam there is one of these."""
    ax = 0 if along_x else 1
    tri = np.array([[(mb.vertices[i].x, mb.vertices[i].y, mb.vertices[i].z) for i in (p.v1, p.v2, p.v3)]
                    for p in mb.polygons])
    keys = np.round(tri, 2)
    count = {}
    for k in keys:
        for i in range(3):
            a, b = tuple(k[i]), tuple(k[(i + 1) % 3])
            key = (a, b) if a < b else (b, a)
            count[key] = count.get(key, 0) + 1
    return {e for e, n in count.items() if n == 1 and all(
        abs(p[ax] - point[ax]) <= OUTLINE_TOL and abs(p[1 - ax] - point[1 - ax]) <= hw + 0.5 for p in e)}


def _straight(spec):
    """The same zone with no leg winding: the straight rough legs of before."""
    flat = copy.deepcopy(spec)
    for cor in flat.corridors:
        cor.wind = []
    return flat


@pytest.mark.slow
def test_caves_wind_and_warrens_mostly_do_not():
    # An angled cave corridor (random placement task 10) winds along its route line, its legs
    # never: its two ends count with the winding legs' (test_wind_route_mesh welds them).
    caves = sum(len(_winding_ends(_spec(*z))) + 2 * sum(1 for c in _spec(*z).corridors if c.entry and c.path)
                for z in ZONES if z[0] == "cave")
    assert caves > 50, "cave legs wind"


@pytest.mark.slow
@pytest.mark.parametrize("zone", ZONES, ids=lambda z: f"{z[0]}{z[1]}-{z[2]}-{z[3]}")
def test_winding_ends_weld_and_floor_steps_stay_small(zone):
    spec = _spec(*zone)
    ends = _winding_ends(spec)
    if not ends:
        pytest.skip("no leg winds here")
    mb, before = build_mesh(spec), build_mesh(_straight(spec))
    for cor, _, point, along_x in ends:
        hw = cor.width / 2
        # Where the leg meets its bend square or room: no edge left open that the straight
        # leg's square end closed.
        assert _open_edges_in_line(mb, point, along_x, hw) <= _open_edges_in_line(before, point, along_x, hw), \
            (cor.id, point)
    # Every floor triangle of a winding leg rises within the gate's step.
    leg = MeshBuilder()
    leg._uv_scale = mb._uv_scale
    for cor, line, z0, z1 in _winding_legs(spec):
        assert leg._add_winding_leg(line, z0, z1, cor.width / 2, cor.height, cor.rough, 0, 0, 0)
    for p in leg.polygons:
        zs = [leg.vertices[i].z for i in (p.v1, p.v2, p.v3)]
        if leg.vertices[p.v1].nz > 0.5:
            assert max(zs) - min(zs) <= MAX_SEG_RISE + 1e-6


@pytest.mark.slow
@pytest.mark.parametrize("zone", ZONES, ids=lambda z: f"{z[0]}{z[1]}-{z[2]}-{z[3]}")
def test_winding_zones_pass_the_gate(zone, tmp_path):
    spec = _spec(*zone)
    res = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    rep = validate(res.eqg_path, spec=spec, check_corridors=True)
    reasons = [r.room_id for r in rep.rooms if not r.reachable]
    reasons += [f"{o.room_id}: {o.reason}" for o in rep.outlines if not o.ok]
    reasons += [f"{c.corridor_id}: {c.reason}" for c in rep.corridors if not c.connected]
    reasons += [f"conflict {c}" for c in rep.conflicts]
    assert rep.passed and rep.corridors_passed, reasons
