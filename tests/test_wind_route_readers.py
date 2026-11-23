"""Winding routes task 3 (Requirement 4; design "Readers"): what reads a corridor follows its
route line (``CorridorSpec.path``) when it has one. Corridor RoomContexts rasterise the line's
strip, so decor stands in the tunnel; the map SVG draws the line; the outline (so the EQ map)
traces the strip's walls.

Task 2 lays the mesh along the path in parallel, so the build tests here hold against ``path``
and the spec, not the mesh: no floor cell, wall or Prop off the strip. The outline is tested on
a synthetic path-strip mesh (float32, as a TER is read back).
"""

import functools
import math
import re

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from core.ter import Material, Polygon, TerFile, Vertex
from generators.backends import backend_for
from generators.eqmap import build_map_file
from generators.mapgeom import DepthBand, OutlineSet, extract_outline
from generators.mapview import corridor_path, render_map_svg
from generators.pipeline import _with_decor
from generators.room_context import _in_polygon, corridor_contexts
from generators.routing import Route, TunnelRules, corridor_route, door_ends, strip_corners, wind_route
from generators.zone_spec import ZoneSpec

ROUGH = TunnelRules((20.0, 72.0), 60.0, 0.2, 20.0)
SEEDS = range(5)
TOL = 0.05          # a cell this near a strip's edge may fall either side of it (u)


# --- Cave builds -------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _cave(seed, rooms=12):
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "dungeon_theme": "cave", "layout": "graph",
                                   "room_count": rooms}, [])
    plan.name = "router"
    spec = _with_decor(plan_to_spec(plan, seed=seed, warnings=[]))
    ter = backend_for(spec.zone_type).build(spec, "ter_router", 2)
    return spec, ter


def _paths(spec):
    return {c.id: c for c in spec.corridors if len(c.path) >= 2}


def _strip(cor, grow=0.0):
    """The path's strip in plan, from ``routing.strip_corners`` (as the mesh and the clearance
    check build it), apart from ``room_context``: left side out, right side back."""
    corners = strip_corners(cor.path, cor.width / 2 + grow)
    assert corners is not None
    return [c[0] for c in corners] + [c[1] for c in corners][::-1]


def _on_strip(x, y, cor, grow):
    return _in_polygon(np.asarray(x, float), np.asarray(y, float), _strip(cor, grow))


def test_some_cave_corridor_has_a_path():
    assert any(_paths(_cave(seed)[0]) for seed in SEEDS)


@pytest.mark.parametrize("seed", SEEDS)
def test_path_corridor_floor_cells_lie_on_the_strip(seed):
    """Every path corridor's floor cell, wall face and doorway lies on its path's strip, none
    off it: not on a straight leg's rect or a step 23 winding leg the path leaves."""
    spec, ter = _cave(seed)
    paths = _paths(spec)
    ctxs = {c.id: c for c in corridor_contexts(spec, ter)}
    for cid, cor in paths.items():
        ctx = ctxs[cid]
        nx, ny = ctx.floor.shape
        gx, gy = np.meshgrid(ctx.origin[0] + np.arange(nx) * ctx.cell,
                             ctx.origin[1] + np.arange(ny) * ctx.cell, indexing="ij")
        floor = ~np.isnan(ctx.floor)
        assert not (floor & ~_on_strip(gx, gy, cor, TOL)).any(), f"seed {seed} {cid}: floor off the strip"
        if ctx.walls:
            wx = np.array([w.x for w in ctx.walls])
            wy = np.array([w.y for w in ctx.walls])
            assert _on_strip(wx, wy, cor, 0.2).all(), f"seed {seed} {cid}: a wall off the strip"
        # The context's box holds the strip (it is the strip's bounds, nothing of the legs).
        plan = np.array(_strip(cor))
        x0, y0, _z0, x1, y1, _z1 = ctx.box
        assert x0 == pytest.approx(plan[:, 0].min(), abs=0.01) and x1 == pytest.approx(plan[:, 0].max(), abs=0.01)
        assert y0 == pytest.approx(plan[:, 1].min(), abs=0.01) and y1 == pytest.approx(plan[:, 1].max(), abs=0.01)
        assert len(ctx.doors) == 2


def test_path_corridors_have_floor():
    """The run-outs lie on the route's own first and last legs, so even before the path's
    own mesh a path corridor reads floor there."""
    seen = 0
    for seed in SEEDS:
        spec, ter = _cave(seed)
        paths = _paths(spec)
        for ctx in corridor_contexts(spec, ter):
            if ctx.id in paths:
                seen += 1
                assert (~np.isnan(ctx.floor)).any(), f"seed {seed} {ctx.id}: no floor"
    assert seen


# --- Decor -------------------------------------------------------------------------------

def _install():
    from generators.decor.stock import eq_path_from_env
    return eq_path_from_env()


def _check_props(seed, ctx, props, cor):
    """Each Prop of a path corridor stands on its strip: a floor Prop's whole plan, a wall
    Prop's origin (at its wall, a little out from it)."""
    for p in props:
        if p.mount == "wall":
            ok = bool(_on_strip(p.x, p.y, cor, 1.0))
        else:
            c, s = math.cos(p.yaw), math.sin(p.yaw)
            corners = [(p.x + c * u - s * v, p.y + s * u + c * v)
                       for u in (-p.w / 2, p.w / 2) for v in (-p.d / 2, p.d / 2)]
            ok = all(_on_strip(x, y, cor, TOL) for x, y in corners)
        assert ok, f"seed {seed} {ctx.id}: {p.key} at ({p.x}, {p.y}) is off the strip"


def test_lights_placed_in_a_path_corridor_stand_on_its_strip():
    """A cave's corridors are dark (``layers/cave.toml``), so the base rules light the 5 caves'
    path corridors here: every Prop placed from their contexts is on the strip."""
    from generators.decor.placement import place

    seen = 0
    for seed in SEEDS:
        spec, ter = _cave(seed)
        paths = _paths(spec)
        for ctx in corridor_contexts(spec, ter):
            if ctx.id in paths:
                d = place(ctx, control="dense", may_be_bare=False)
                _check_props(seed, ctx, d.props, paths[ctx.id])
                seen += len(d.props)
    assert seen, "no Prop on a path corridor to check"


@pytest.mark.skipif(_install() is None, reason="EQ_PATH is not set (no EQ install to read)")
def test_decor_places_no_path_corridor_prop_off_the_strip():
    """Decor on 5 cave builds (the Decor control resolved as a sweep build resolves it,
    ``pipeline._with_decor``): no Prop of a path corridor stands off its strip."""
    from generators.builder import decor_for

    for seed in SEEDS:
        spec, ter = _cave(seed)
        paths = _paths(spec)
        warnings = []
        built = decor_for(spec, ter, warnings)
        assert built is not None, warnings
        for ctx, d, _problems in built.rooms:
            if ctx.source == "corridor" and ctx.id in paths:
                _check_props(seed, ctx, d.props, paths[ctx.id])


# --- Map SVG -----------------------------------------------------------------------------

def _plain_outline(spec):
    xs = [v for r in spec.rooms for v in (r.bounds[0][0], r.bounds[1][0])]
    ys = [v for r in spec.rooms for v in (r.bounds[0][1], r.bounds[1][1])]
    return OutlineSet((), (DepthBand(0, -math.inf, math.inf, 0.0, "main", 0),),
                      (min(xs), min(ys), 0.0, max(xs), max(ys), 0.0), 0, True)


@pytest.mark.parametrize("seed", SEEDS)
def test_map_svg_draws_the_path(seed):
    """Over an outline, a path corridor's line is its path, opening to opening (whatever its
    ``wind``), and the SVG draws it point for point."""
    spec, _ter = _cave(seed)
    rooms = {r.id: r for r in spec.rooms}
    paths = _paths(spec)
    for cid, cor in paths.items():
        assert corridor_path(cor, rooms) == [tuple(p) for p in cor.path]
        a, b = door_ends(corridor_route(cor, rooms))    # an angled end: on the wall plane
        assert cor.path[0] == pytest.approx(a) and cor.path[-1] == pytest.approx(b)
    svg = render_map_svg(spec, outline=_plain_outline(spec))
    lines = re.findall(r'<polyline (?:class="threshold" )?points="([^"]*)"', svg)
    assert len(lines) == len(spec.corridors)
    drawn = sorted(len(m.split()) for m in lines)
    assert drawn == sorted(len(corridor_path(c, rooms)) for c in spec.corridors)


# --- The outline and EQ map on a path strip ----------------------------------------------

def _path_ter(seed, rise):
    """A route line's strip mesh, far off the origin and read back from bytes (float32): an
    L route wound by ``wind_route``, each run's floor in three quads (flat over the run-outs,
    the rise spread by length between, as task 2 lays it), a wall on each side of each quad,
    a wall across each end. Returns the TER, the line, and the strip's sides."""
    hw = 8.0
    ox, oy = 1000.0, -700.0
    route = Route(((ox, oy), (ox + 220.0, oy), (ox + 220.0, oy + 200.0)), (True, False), -1, "l")
    line = wind_route(route, hw, ROUGH, f"route-readers{seed}")
    assert line is not None
    corners = strip_corners(line, hw)
    assert corners is not None
    left = [np.array(c[0]) for c in corners]
    right = [np.array(c[1]) for c in corners]
    seg = [math.dist(line[j], line[j + 1]) for j in range(len(line) - 1)]
    s0, s1 = seg[0], sum(seg) - seg[-1]

    def z_at(s):
        return 0.0 if s <= s0 else rise if s >= s1 else rise * (s - s0) / (s1 - s0)

    ter = TerFile(name="route")
    ter.materials.append(Material(index=0, name="floor"))

    def quad(*corners):
        k = len(ter.vertices)
        ter.vertices.extend(Vertex(float(x), float(y), float(z)) for x, y, z in corners)
        ter.polygons += [Polygon(k, k + 1, k + 2), Polygon(k, k + 2, k + 3)]

    def at(side, i, f):
        return side[i] + (side[i + 1] - side[i]) * f

    done = 0.0
    for i in range(len(line) - 1):
        for s in range(3):
            za, zb = z_at(done + seg[i] * s / 3), z_at(done + seg[i] * (s + 1) / 3)
            l0, l1 = at(left, i, s / 3), at(left, i, (s + 1) / 3)
            r0, r1 = at(right, i, s / 3), at(right, i, (s + 1) / 3)
            quad((*r0, za), (*r1, zb), (*l1, zb), (*l0, za))
            quad((*l0, za), (*l1, zb), (*l1, zb + 12), (*l0, za + 12))
            quad((*r1, zb), (*r0, za), (*r0, za + 12), (*r1, zb + 12))
        done += seg[i]
    for (a, b), z in (((right[0], left[0]), 0.0), ((left[-1], right[-1]), rise)):
        quad((*a, z), (*b, z), (*b, z + 12), (*a, z + 12))
    return TerFile.from_bytes(ter.to_bytes(), name="route"), line, left, right


def _seg_dist(p, a, b):
    p, a, b = (np.asarray(v, float)[:2] for v in (p, a, b))
    ab = b - a
    t = min(1.0, max(0.0, float((p - a) @ ab) / float(ab @ ab)))
    return float(np.linalg.norm(p - a - t * ab))


@pytest.mark.parametrize("rise", [0.0, 24.0])
@pytest.mark.parametrize("seed", range(8))
def test_outline_and_eq_map_trace_the_path_walls(seed, rise):
    """The path strip's walls come out as walls, each once: as long as the strip's sides and
    ends, every point of a side on one (its chamfered bends included), and the EQ map draws
    the same lines."""
    ter, line, left, right = _path_ter(seed, rise)
    start = (line[0][0] + 3.0, line[0][1])
    out = extract_outline(ter, (*start, 0.25))
    walls = [p for p in out.polylines if p.kind == "wall"]
    sides = sum(float(np.linalg.norm(s[i + 1] - s[i])) for s in (left, right) for i in range(len(s) - 1))
    want = sides + 2 * 2 * 8.0
    assert sum(math.dist(p[:2], q[:2]) for pl in walls for p, q in zip(pl.points, pl.points[1:])) \
        == pytest.approx(want, abs=0.05)
    assert sum(p.length for p in out.polylines if p.kind == "ledge") < 0.01
    segs = [(p, q) for pl in walls for p, q in zip(pl.points, pl.points[1:])]
    for side in (left, right):
        for i in range(len(side) - 1):
            for f in (0.1, 0.5, 0.9):
                pt = side[i] + (side[i + 1] - side[i]) * f
                assert min(_seg_dist(pt, p, q) for p, q in segs) < 0.01
    mf = build_map_file(out, ZoneSpec(name="route"), "route")
    lines = [ln for layer in mf.layers for ln in layer.lines]
    length = sum(math.hypot(ln.x2 - ln.x1, ln.y2 - ln.y1) for ln in lines)
    assert length == pytest.approx(sum(math.dist(p[:2], q[:2]) for pl in out.polylines
                                       for p, q in zip(pl.points, pl.points[1:])), abs=0.05)
