"""Winding control task 1 (Requirements 1-4; design "Data", "Scaled rules"): the plan's
``winding`` reaches the spec, scales the tunnel's wander for the clearance measure, and every
reader that re-winds a leg (mesh, decor RoomContexts, map) winds it by the same scaled rules.
"""

import functools
import math

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.schema import WINDING_MAX, ZonePlan
from generators import layout, mapview
from generators.backends import backend_for
from generators.geometry import MeshBuilder
from generators.mapgeom import DepthBand, OutlineSet
from generators.mapview import corridor_path
from generators.room_context import _in_polygon, _strip_plan, corridor_contexts
from generators.routing import angled, corridor_route, strip_corners, tunnel_for, winding_legs
from generators.wall_styles import tunnel_rules, tunnel_rules_for
from generators.zone_spec import ZoneSpec

SEEDS = range(5)
TOL = 0.05


@functools.lru_cache(maxsize=None)
def _cave(seed, winding=None, run=None):
    controls = {"zone_type": "dungeon", "dungeon_theme": "cave", "layout": "graph", "room_count": 12}
    if winding is not None:
        controls["winding"] = winding
    plan = ZonePlan.from_controls(controls, [])
    plan.name = "windc"
    saved = layout.PROFILE_RUN_FACTOR["cave"], layout.WINDING_RUN
    if run is not None:                     # pin the run: no Winding coupling
        layout.PROFILE_RUN_FACTOR["cave"], layout.WINDING_RUN = run, 0.0
    try:
        return plan_to_spec(plan, seed=seed, warnings=[])
    finally:
        layout.PROFILE_RUN_FACTOR["cave"], layout.WINDING_RUN = saved


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d2 = dx * dx + dy * dy
    t = 0.0 if d2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _stray(spec):
    """Corridor id -> the largest sideways stray of its centreline (route line or wound legs,
    as the map draws it) off its straight route, at the line's vertices."""
    rooms = {r.id: r for r in spec.rooms}
    out = {}
    for cor in spec.corridors:
        wps = list(corridor_route(cor, rooms).waypoints)
        line = corridor_path(cor, rooms, tunnel_for(cor, spec))
        out[cor.id] = max(min(_seg_dist(p, a, b) for a, b in zip(wps, wps[1:])) for p in line)
    return out


# --- The plan and the spec -----------------------------------------------------------------

def test_plan_clamps_and_falls_back():
    assert ZonePlan().validate().winding == 1.0
    assert ZonePlan(winding=-3).validate().winding == 0.0
    assert ZonePlan(winding=99).validate().winding == WINDING_MAX
    for bad in ("twisty", None, True, float("nan")):
        assert ZonePlan(winding=bad).validate().winding == 1.0
    assert "winding" not in ZonePlan().validate().to_dict()
    assert ZonePlan.from_dict(ZonePlan(winding=1.5).validate().to_dict()).winding == 1.5


def test_a_spec_without_winding_loads_as_one_and_writes_no_key():
    spec = ZoneSpec.from_dict(ZoneSpec(name="w").to_dict())
    assert spec.winding == 1.0 and "winding" not in spec.to_dict()
    spec.winding = 0.5
    again = ZoneSpec.from_dict(spec.to_dict())
    assert again.winding == 0.5 and again.to_dict()["winding"] == 0.5


def test_scaled_rules_are_the_stock_object_at_one_and_none_at_zero():
    stock = tunnel_rules()
    assert tunnel_rules_for(ZoneSpec(name="w")) is stock
    assert tunnel_rules_for(ZoneSpec(name="w", winding=0.0)) is None
    two = tunnel_rules_for(ZoneSpec(name="w", winding=2.0))
    assert (two.segment, two.max_turn, two.end) == (stock.segment, stock.max_turn, stock.end)
    assert two.wander == pytest.approx(2 * stock.wander)


# --- The measure ---------------------------------------------------------------------------

@pytest.mark.slow
def test_winding_zero_one_two():
    """0: no corridor has a wind or a path. 1: the zone a plan without the field builds, with
    no key on the spec. 2 on the same run (the coupling pinned off, so the rooms stand where
    they do at 1): the largest stray per corridor is never smaller than at 1."""
    for seed in SEEDS:
        zero, one, base = _cave(seed, 0.0), _cave(seed, 1.0), _cave(seed)
        two = _cave(seed, 2.0, layout.PROFILE_RUN_FACTOR["cave"])
        assert zero.winding == 0.0 and two.winding == 2.0
        # An angled corridor (random placement task 10) has its entry line as a path at 0.
        assert all(not c.wind and (not c.path or angled(c)) for c in zero.corridors), seed
        assert one.to_dict() == base.to_dict() and "winding" not in one.to_dict()
        s1, s2 = _stray(one), _stray(two)
        assert s1.keys() == s2.keys()
        # Per corridor, where it's read along its legs (each leg's wander clipped at a limit
        # that doubles). A route line (step 25) is drawn afresh at each wander and an angled
        # one strays by its entry angle at any Winding: neither is monotone, so they count
        # only in the aggregate below (random placement task 10's layout gives one square
        # route line at seed 0 that strays 20.1 at 1 and 18.5 at 2).
        legs = {c.id for c in one.corridors if not c.path and not angled(c)}
        for cid in legs:
            assert s2[cid] >= s1[cid] - 1e-6, (seed, cid, s1[cid], s2[cid])
    assert any(s2[c] > s1[c] + 0.1 for c in s1), "winding 2 strays no further anywhere"


def test_cave_run_follows_winding_above_one():
    """Task 2's coupling: the cave run is 4 widths at any Winding up to 1 and grows by
    ``WINDING_RUN`` per unit above; a profile without a run keeps the embed default."""
    for k in (0.0, 0.5, 1.0):
        assert layout.profile_run_factor("cave", k) == layout.PROFILE_RUN_FACTOR["cave"]
    assert layout.profile_run_factor("cave", 2.0) == pytest.approx(
        layout.PROFILE_RUN_FACTOR["cave"] + layout.WINDING_RUN)
    assert layout.profile_run_factor(None, 2.0) is None
    assert layout.profile_run_factor("dungeon", 2.0) is None


@pytest.mark.slow
def test_winding_two_strays_clearly_more_than_one():
    """Over ten caves, the rough corridors at 2 stray clearly further than at 1: the mean and
    p90 of the largest stray per corridor (the median is 0 at both, most cave corridors being
    Z diagonals with no room to wander), and more of them wind. Square ones only: an angled
    corridor (random placement task 10) strays off its route by its entry angle at any
    Winding."""
    def stats(k):
        cors = [(_stray(s)[c.id], bool(c.path) or any(c.wind))
                for s in (_cave(seed, k) for seed in range(10)) for c in s.corridors
                if c.rough > 0 and not angled(c)]
        strays = sorted(x for x, _ in cors)
        return (sum(strays) / len(strays), strays[int(0.9 * (len(strays) - 1))],
                sum(w for _, w in cors) / len(cors))
    mean1, p90_1, wind1 = stats(1.0)
    mean2, p90_2, wind2 = stats(2.0)
    assert mean2 > 1.5 * mean1, (mean1, mean2)
    assert p90_2 > 1.25 * p90_1, (p90_1, p90_2)
    assert wind2 > wind1, (wind1, wind2)


# --- The readers agree at 2 ----------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _built(seed):
    """A cave at winding 2 on step 23's long run (9 widths), its corridors read along their
    legs (no route line), and its TER."""
    spec = _cave(seed, 2.0, 9.0)
    for cor in spec.corridors:
        cor.path = []
    return spec, backend_for(spec.zone_type).build(spec, f"ter_windc{seed}", 2)


def _legs(spec):
    """(corridor, leg index, scaled line, stock line) of each leg the spec winds."""
    rooms = {r.id: r for r in spec.rooms}
    out = []
    for cor in spec.corridors:
        scaled, stock = winding_legs(cor, rooms, tunnel_for(cor, spec)), winding_legs(cor, rooms)
        out += [(cor, k, line, stock[k]) for k, line in enumerate(scaled) if line is not None]
    return out


def test_scaled_legs_differ_from_stock_somewhere():
    """The agreement tests below have teeth: some leg at 2 winds past the stock clip."""
    assert any(stock != line for s in SEEDS for _, _, line, stock in _legs(_built(s)[0]))


@pytest.mark.parametrize("seed", SEEDS)
def test_mesh_lays_the_scaled_strip(seed):
    """Each corner of each scaled winding strip is a vertex of the built mesh."""
    spec, ter = _built(seed)
    xy = np.array([(v.x, v.y) for v in ter.vertices])
    for cor, k, line, _ in _legs(spec):
        for corner in (c for pair in strip_corners(line, cor.width / 2) for c in pair):
            assert np.min(np.hypot(*(xy - corner).T)) < TOL, (seed, cor.id, k, corner)


@pytest.mark.parametrize("seed", SEEDS)
def test_decor_cells_lie_on_the_scaled_strip(seed):
    """Every floor cell of a winding corridor's RoomContext lies on its scaled strips, its
    straight legs or its bend squares."""
    spec, ter = _built(seed)
    rooms = {r.id: r for r in spec.rooms}
    ctxs = {c.id: c for c in corridor_contexts(spec, ter)}
    winding = {cor.id for cor, *_ in _legs(spec)}
    for cor in spec.corridors:
        if cor.id not in winding or cor.id not in ctxs:
            continue
        ctx = ctxs[cor.id]
        nx, ny = ctx.floor.shape
        gx, gy = np.meshgrid(ctx.origin[0] + np.arange(nx) * ctx.cell,
                             ctx.origin[1] + np.arange(ny) * ctx.cell, indexing="ij")
        route = corridor_route(cor, rooms)
        wps, hw = list(route.waypoints), cor.width / 2
        on = np.zeros(gx.shape, bool)
        for k, line in enumerate(winding_legs(cor, rooms, tunnel_for(cor, spec))):
            if line is not None:
                on |= _in_polygon(gx, gy, _strip_plan(line, hw + TOL))
                continue
            (ax, ay), (bx, by) = wps[k], wps[k + 1]
            r = (min(ax, bx), ay - hw, max(ax, bx), ay + hw) if route.axes[k] else \
                (ax - hw, min(ay, by), ax + hw, max(ay, by))
            on |= (gx >= r[0] - TOL) & (gx <= r[2] + TOL) & (gy >= r[1] - TOL) & (gy <= r[3] + TOL)
        for i in range(1, len(wps) - 1):
            x0, y0, x1, y1 = MeshBuilder._bend_square(wps, i, hw)
            on |= (gx >= x0 - TOL) & (gx <= x1 + TOL) & (gy >= y0 - TOL) & (gy <= y1 + TOL)
        floor = ~np.isnan(ctx.floor)
        assert floor.any() and not (floor & ~on).any(), (seed, cor.id)


@pytest.mark.parametrize("seed", SEEDS)
def test_map_line_runs_the_scaled_legs(seed, monkeypatch):
    """The map SVG's line for each winding corridor holds every point of its scaled legs, in
    order."""
    spec, _ter = _built(seed)
    rooms = {r.id: r for r in spec.rooms}
    drawn = {}

    def spy(c, by_id, rules=None):
        drawn[c.id] = corridor_path(c, by_id, rules)
        return drawn[c.id]

    monkeypatch.setattr(mapview, "corridor_path", spy)
    xs = [v for r in spec.rooms for v in (r.bounds[0][0], r.bounds[1][0])]
    ys = [v for r in spec.rooms for v in (r.bounds[0][1], r.bounds[1][1])]
    outline = OutlineSet((), (DepthBand(0, -math.inf, math.inf, 0.0, "main", 0),),
                         (min(xs), min(ys), 0.0, max(xs), max(ys), 0.0), 0, True)
    mapview.render_map_svg(spec, outline=outline)
    for cor in {id(c): c for c, *_ in _legs(spec)}.values():
        pts = [p for line in winding_legs(cor, rooms, tunnel_for(cor, spec)) if line for p in line]
        it = iter(drawn[cor.id])
        assert all(any(q == p for q in it) for p in pts), (seed, cor.id)


# --- Framed corridors wind (task 9, Requirement 8) ----------------------------------------

# A straight seam and a breach, a Z seam and a Z breach, a straight and a Z frame. Re-pinned
# by random placement task 1 (a cave's offsets now salt with the build's seed: seeds 2 and 12
# lost their cases).
#: Re-pinned from (6, 23, 55) by random placement task 11: room sizes vary, so seed 23's and
#: 55's layouts moved and no straight Breach held a path (over cave seeds 0-79 the held share
#: is 97 of 133 against master's 89 of 124).
FRAMED_SEEDS = (3, 6, 19)


@functools.lru_cache(maxsize=None)
def _framed(seed):
    spec = _cave(seed)
    return spec, backend_for(spec.zone_type).build(spec, f"ter_framed{seed}", 2)


def _along(line, p):
    """How far along polyline ``line`` its nearest point to ``p`` lies, and how far off it."""
    best, done = (math.inf, 0.0), 0.0
    for a, b in zip(line, line[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        t = 0.0 if length < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) +
                                                          (p[1] - a[1]) * (b[1] - a[1])) / length ** 2))
        off = math.hypot(p[0] - a[0] - t * (b[0] - a[0]), p[1] - a[1] - t * (b[1] - a[1]))
        if off < best[0]:
            best = (off, done + t * length)
        done += length
    return best[1], best[0]


def _floor_under(ter, p):
    """(z, material name) of the floor triangle of ``ter`` holding plan point ``p``, nearest
    from above at ``p``'s height if it has one (``p`` = (x, y, z))."""
    best = None
    for poly in ter.polygons:
        a, b, c = (ter.vertices[i] for i in (poly.v1, poly.v2, poly.v3))
        det = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
        if abs(det) < 1e-9:
            continue
        l1 = ((b.y - c.y) * (p[0] - c.x) + (c.x - b.x) * (p[1] - c.y)) / det
        l2 = ((c.y - a.y) * (p[0] - c.x) + (a.x - c.x) * (p[1] - c.y)) / det
        l3 = 1.0 - l1 - l2
        if min(l1, l2, l3) < -1e-6:
            continue
        nz = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
        if nz <= 0:
            continue                        # a floor faces up
        z = l1 * a.z + l2 * b.z + l3 * c.z
        if best is None or abs(z - p[2]) < abs(best[0] - p[2]):
            best = (z, ter.materials[poly.material].name)
    return best


def test_framed_corridors_take_a_path_on_the_test_seeds():
    """The cases below have teeth: every form, straight and Z routes, a split Seam."""
    seen = set()
    for seed in FRAMED_SEEDS:
        spec, _ = _framed(seed)
        rooms = {r.id: r for r in spec.rooms}
        for cor in spec.corridors:
            if cor.transition is not None and cor.path:
                seen.add((cor.transition.form, bool(cor.transition.floor_material),
                          len(corridor_route(cor, rooms).waypoints) > 2))
    assert {("seam", True, False), ("seam", True, True), ("frame", False, True), ("breach", False, False)} <= seen


@pytest.mark.parametrize("seed", FRAMED_SEEDS)
def test_framed_line_stands_square_and_every_reader_reads_it(seed, monkeypatch):
    """A corridor holding a Transition line has a path straight along the line's axis for
    its depth and a half-width either side, through the line. The mesh splits a Seam there
    (each look on its own side, its floor at the line's ``z``); ``corridor_continuity`` and
    the walk through the line pass; the decor context has floor through the line and its
    jambs on it; the map's door spot stands across the drawn line, square to it."""
    from analyzer.traverse import AgentModel, build_walk_surface, check_transition, corridor_continuity

    spec, ter = _framed(seed)
    held = [c for c in spec.corridors if c.transition is not None and c.path]
    assert held, seed
    agent = AgentModel()
    surf = build_walk_surface(ter, agent)
    cont = {r.corridor_id: r for r in corridor_continuity(surf, spec, agent)}
    ctxs = {c.id: c for c in corridor_contexts(spec, ter)}
    for cor in held:
        t, hw = cor.transition, cor.width / 2
        p, d = (t.x, t.y), ((1.0, 0.0) if t.along_x else (0.0, 1.0))
        path = [tuple(q) for q in cor.path]
        s_p, off = _along(path, p)
        assert off < 1e-3, (seed, cor.id)
        total = _along(path, path[-1])[0]
        reach = t.depth + hw
        a, b = min(zip(path, path[1:]), key=lambda ab: _seg_dist(p, *ab))
        u = ((b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b))
        assert abs(u[0] * d[0] + u[1] * d[1]) > 1 - 1e-9, (seed, cor.id, u)      # square to the line
        for s in np.linspace(max(-reach, -s_p), min(reach, total - s_p), 9):
            q = (p[0] + u[0] * s, p[1] + u[1] * s)
            s_q, off_q = _along(path, q)
            assert off_q < 1e-3 and abs(s_q - s_p - s) < 1e-3, (seed, cor.id, s)

        # Mesh: the floor at the line is the line's z; a Seam's two looks either side of it.
        z, _ = _floor_under(ter, (*p, t.z))
        assert abs(z - t.z) < 0.01, (seed, cor.id, z, t.z)
        if t.floor_material:
            near = min(reach - 0.5, 4.0)
            before, after = (p[0] - u[0] * near, p[1] - u[1] * near), (p[0] + u[0] * near, p[1] + u[1] * near)
            assert _floor_under(ter, (*before, t.z))[1] == spec.materials[cor.floor_material].name
            assert _floor_under(ter, (*after, t.z))[1] == spec.materials[t.floor_material].name

        # Continuity and the walk through the line.
        assert cont[cor.id].connected, (seed, cor.id, cont[cor.id].reason)
        assert check_transition(surf, cor, spec, agent).ok, (seed, cor.id)

        # Decor: floor through the line, the jambs standing on it.
        ctx = ctxs[cor.id]
        for s in (-t.depth, 0.0, t.depth):
            x, y = p[0] + d[0] * s, p[1] + d[1] * s
            i, j = (int(round((v - o) / ctx.cell)) for v, o in zip((x, y), ctx.origin))
            assert not np.isnan(ctx.floor[i, j]), (seed, cor.id, s)
        for f in (f for f in ctx.features if f["kind"] == "opening"):
            along = [q[0] if t.along_x else q[1] for q in f["plan"]]
            assert min(along) == pytest.approx(p[0 if t.along_x else 1] - t.depth, abs=0.01)
            assert max(along) == pytest.approx(p[0 if t.along_x else 1] + t.depth, abs=0.01)

    # Map: each door spot's bar crosses a drawn corridor line at its middle, square to it.
    xs = [v for r in spec.rooms for v in (r.bounds[0][0], r.bounds[1][0])]
    ys = [v for r in spec.rooms for v in (r.bounds[0][1], r.bounds[1][1])]
    outline = OutlineSet((), (DepthBand(0, -math.inf, math.inf, 0.0, "main", 0),),
                         (min(xs), min(ys), 0.0, max(xs), max(ys), 0.0), 0, True)
    svg = mapview.render_map_svg(spec, outline=outline)
    import re
    lines = [[tuple(map(float, q.split(","))) for q in m.split()]
             for m in re.findall(r'<polyline[^>]*points="([^"]+)"', svg)]
    bars = [tuple(map(float, m)) for m in
            re.findall(r'class="door-spot" x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"', svg)]
    frames = [c for c in held if c.transition.form == "frame"]
    assert len(bars) >= len(frames)
    for x1, y1, x2, y2 in bars:
        mid = ((x1 + x2) / 2, (y1 + y2) / 2)
        line = min(lines, key=lambda ln: _along(ln, mid)[1])
        assert _along(line, mid)[1] < 0.2, (seed, mid)
        a = min(zip(line, line[1:]), key=lambda ab: _seg_dist(mid, *ab))
        run = (a[1][0] - a[0][0], a[1][1] - a[0][1])
        dot = (run[0] * (x2 - x1) + run[1] * (y2 - y1)) / (math.hypot(*run) * math.hypot(x2 - x1, y2 - y1))
        assert abs(dot) < 0.05, (seed, mid, dot)
