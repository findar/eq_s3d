"""Winding tunnels task 4 (Requirement 4; design "Readers"): what reads a corridor follows a
winding leg. Corridor RoomContexts rasterise the strip ``routing.winding_legs`` gives (so decor
stands on the tunnel's floor), the map SVG draws the tunnel's centreline, and the outline (so
the EQ map) traces angled walls.

Until task 3's winding mesh lands a cave's mesh is still straight, so the build tests here
hold against ``winding_legs`` and the spec: no floor cell off the strip, and the strip's floor
wherever the straight leg's mesh lies under it. The outline is tested on a synthetic angled
tunnel mesh (float32, as a TER is read back).
"""

import functools
import math
import re

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from tests.pbt_helpers import scaled

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from core.ter import Material, Polygon, TerFile, Vertex
from generators import layout
from generators.backends import backend_for
from generators.eqmap import build_map_file
from generators.geometry import MeshBuilder
from generators.mapgeom import DepthBand, OutlineSet, extract_outline
from generators.mapview import corridor_path, render_map_svg
from generators.room_context import _in_polygon, _strip_plan, corridor_contexts
from generators.routing import TunnelRules, corridor_route, wind_leg, winding_legs
from generators.zone_spec import ZoneSpec

ROUGH = TunnelRules((20.0, 72.0), 60.0, 0.2, 20.0)
SEEDS = range(5)
TOL = 0.05          # a cell this near a strip's edge may fall either side of it (u)


# --- The strip ---------------------------------------------------------------------------

def _mitred(line, hw):
    """The strip round ``line``, worked out apart from ``room_context``: each corner off the
    bisector of its two segments by hw over the cosine of half the turn."""
    pts = np.asarray(line, float)
    left, right = [], []
    for i in range(len(pts)):
        ds = []
        if i > 0:
            ds.append(pts[i] - pts[i - 1])
        if i < len(pts) - 1:
            ds.append(pts[i + 1] - pts[i])
        ds = [d / np.linalg.norm(d) for d in ds]
        t = sum(ds) / np.linalg.norm(sum(ds))
        n = np.array([-t[1], t[0]])
        reach = hw / float(t @ ds[0])
        left.append(pts[i] + n * reach)
        right.append(pts[i] - n * reach)
    return left, right


@settings(max_examples=scaled(60), deadline=None)
@given(span=st.floats(80.0, 400.0), hw=st.floats(4.0, 16.0), along_x=st.booleans(),
       back=st.booleans(), seed=st.integers(0, 10_000))
def test_the_strip_is_the_centreline_mitred(span, hw, along_x, back, seed):
    """Each side of the strip runs parallel to its segment, hw off it, and turns on the
    mitre; the ends are square."""
    a = (100.0, -50.0)
    b = (a[0] + (-span if back else span), a[1]) if along_x else (a[0], a[1] + (-span if back else span))
    line = wind_leg(a, b, along_x, hw, 40.0, ROUGH, seed)
    plan = _strip_plan(line, hw)
    left, right = _mitred(line, hw)
    assert np.allclose(plan, left + right[::-1], atol=1e-9)
    for side in (left, right):
        for i in range(len(line) - 1):
            p, q = np.asarray(line[i]), np.asarray(line[i + 1])
            d = (q - p) / np.linalg.norm(q - p)
            for c in (side[i], side[i + 1]):
                r = c - p
                assert abs(r[0] * d[1] - r[1] * d[0]) == pytest.approx(hw, abs=1e-6)


# --- Cave builds -------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _cave(seed, rooms=12):
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "dungeon_theme": "cave", "layout": "graph",
                                   "room_count": rooms}, [])
    plan.name = "windr"
    # Step 23's cave run (9 widths), so the legs are long enough to wind; winding routes task
    # 4 dropped the profile's run to 4, where some of these caves have no winding leg.
    saved = layout.PROFILE_RUN_FACTOR["cave"]
    layout.PROFILE_RUN_FACTOR["cave"] = 9.0
    try:
        spec = plan_to_spec(plan, seed=seed, warnings=[])
    finally:
        layout.PROFILE_RUN_FACTOR["cave"] = saved
    for cor in spec.corridors:       # every route as step 23 lays it: no route line (step 25)
        cor.path = []                # and square ends (random placement task 10's entry)
        cor.entry = []
    ter = backend_for(spec.zone_type).build(spec, "ter_windr", 2)
    return spec, ter


def _shapes(cor, rooms):
    """A corridor's floor in plan, from the route and ``winding_legs`` alone: (winding
    strips as (left, right) sides, the straight legs' and bend squares' rects, each winding
    leg's straight rect)."""
    route = corridor_route(cor, rooms)
    wps, hw = list(route.waypoints), cor.width / 2
    lines = winding_legs(cor, rooms)
    strips, rects, straight = [], [], []
    for k in range(len(wps) - 1):
        (ax, ay), (bx, by) = wps[k], wps[k + 1]
        rect = (min(ax, bx), ay - hw, max(ax, bx), ay + hw) if route.axes[k] else \
            (ax - hw, min(ay, by), ax + hw, max(ay, by))
        if lines[k] is None:
            rects.append(rect)
        else:
            strips.append((lines[k], hw))
            straight.append(rect)
    for i in range(1, len(wps) - 1):
        rects.append(MeshBuilder._bend_square(wps, i, hw))
    return strips, rects, straight


def _in_strip(x, y, line, hw):
    left, right = _mitred(line, hw)
    return _in_polygon(np.asarray(x, float), np.asarray(y, float), [tuple(p) for p in left + right[::-1]])


def _in_rect(x, y, r, grow=0.0):
    x, y = np.asarray(x, float), np.asarray(y, float)
    return (x >= r[0] - grow) & (x <= r[2] + grow) & (y >= r[1] - grow) & (y <= r[3] + grow)


def _on_floor(x, y, strips, rects, grow):
    out = np.zeros(np.shape(x), bool)
    for line, hw in strips:
        out |= _in_strip(x, y, line, hw + grow)
    for r in rects:
        out |= _in_rect(x, y, r, grow)
    return out


def _winding(spec):
    rooms = {r.id: r for r in spec.rooms}
    # A corridor with a route line (step 25, ``path``) is read along it, not its legs.
    return rooms, {c.id: c for c in spec.corridors
                   if not c.path and any(l is not None for l in winding_legs(c, rooms))}


@pytest.mark.parametrize("seed", SEEDS)
def test_corridor_floor_cells_lie_on_the_strip(seed):
    """Every winding corridor's floor cell lies on its strips, straight legs or bend squares,
    none off them (so none on the part of a straight leg the strip leaves); its wall faces
    stand on them too; and a strip's cells over the straight mesh are its floor."""
    spec, ter = _cave(seed)
    rooms, winding = _winding(spec)
    assert winding, "no winding corridor to read"
    boxes = [r.bounds for r in spec.rooms]
    ctxs = {c.id: c for c in corridor_contexts(spec, ter)}
    for cid, cor in winding.items():
        ctx = ctxs[cid]
        strips, rects, straight = _shapes(cor, rooms)
        nx, ny = ctx.floor.shape
        gx, gy = np.meshgrid(ctx.origin[0] + np.arange(nx) * ctx.cell,
                             ctx.origin[1] + np.arange(ny) * ctx.cell, indexing="ij")
        floor = ~np.isnan(ctx.floor)
        on = _on_floor(gx, gy, strips, rects, TOL)
        assert floor.any()
        assert not (floor & ~on).any(), f"seed {seed} {cid}: floor off the strip"
        if ctx.walls:
            wx = np.array([w.x for w in ctx.walls])
            wy = np.array([w.y for w in ctx.walls])
            assert _on_floor(wx, wy, strips, rects, 0.2).all(), f"seed {seed} {cid}: a wall off the strip"
        # The straight mesh lies under each straight rect, so the strip's part of it is floor.
        roomy = np.zeros(gx.shape, bool)
        for (x0, y0, _), (x1, y1, _) in boxes:
            roomy |= _in_rect(gx, gy, (x0, y0, x1, y1), TOL)
        for (line, hw), rect in zip(strips, straight):
            core = _in_strip(gx, gy, line, hw - TOL) & _in_rect(gx, gy, rect, -TOL) & ~roomy
            assert core.any()
            assert floor[core].all(), f"seed {seed} {cid}: strip floor missing"


# --- Decor -------------------------------------------------------------------------------

def _install():
    from generators.decor.stock import eq_path_from_env
    return eq_path_from_env()


def _check_props(seed, ctx, props, cor, rooms):
    """Each Prop of a winding corridor stands on its floor: a floor Prop's whole plan, a wall
    Prop's origin (at its wall, a little out from it)."""
    strips, rects, _ = _shapes(cor, rooms)
    for p in props:
        if p.mount == "wall":
            ok = bool(_on_floor(p.x, p.y, strips, rects, 1.0))
        else:
            c, s = math.cos(p.yaw), math.sin(p.yaw)
            corners = [(p.x + c * u - s * v, p.y + s * u + c * v)
                       for u in (-p.w / 2, p.w / 2) for v in (-p.d / 2, p.d / 2)]
            ok = all(_on_floor(x, y, strips, rects, TOL) for x, y in corners)
        assert ok, f"seed {seed} {ctx.id}: {p.key} at ({p.x}, {p.y}) is off the strip"


@pytest.mark.slow
def test_lights_placed_in_a_winding_corridor_stand_on_its_strip():
    """A cave's corridors are dark (``layers/cave.toml``), so the base rules light the 5 caves'
    winding corridors here: every Prop placed from their contexts is on the strip."""
    from generators.decor.placement import place

    seen = 0
    for seed in SEEDS:
        spec, ter = _cave(seed)
        rooms, winding = _winding(spec)
        for ctx in corridor_contexts(spec, ter):
            if ctx.id in winding:
                d = place(ctx, control="dense", may_be_bare=False)
                _check_props(seed, ctx, d.props, winding[ctx.id], rooms)
                seen += len(d.props)
    assert seen, "no Prop on a winding corridor to check"


@pytest.mark.slow
@pytest.mark.skipif(_install() is None, reason="EQ_PATH is not set (no EQ install to read)")
def test_decor_places_no_corridor_prop_off_the_strip():
    """Decor on 5 cave builds (the build's own rules and settling): no Prop of a winding
    corridor stands off its strip. A cave's corridors are dark today, so this holds the line
    for when they're lit; the test above places lights in them."""
    from generators.builder import decor_for

    for seed in SEEDS:
        spec, ter = _cave(seed)
        spec.decor = "normal"
        rooms, winding = _winding(spec)
        warnings = []
        built = decor_for(spec, ter, warnings)
        assert built is not None, warnings
        for ctx, d, _problems in built.rooms:
            if ctx.source == "corridor" and ctx.id in winding:
                _check_props(seed, ctx, d.props, winding[ctx.id], rooms)


# --- Map SVG -----------------------------------------------------------------------------

def _plain_outline(spec):
    xs = [v for r in spec.rooms for v in (r.bounds[0][0], r.bounds[1][0])]
    ys = [v for r in spec.rooms for v in (r.bounds[0][1], r.bounds[1][1])]
    return OutlineSet((), (DepthBand(0, -math.inf, math.inf, 0.0, "main", 0),),
                      (min(xs), min(ys), 0.0, max(xs), max(ys), 0.0), 0, True)


@pytest.mark.parametrize("seed", SEEDS)
def test_map_svg_draws_the_tunnel(seed):
    """Over an outline, a winding corridor's line runs along its tunnel: every point of its
    winding legs, in order; a corridor that doesn't wind keeps its route's waypoints."""
    spec, _ter = _cave(seed)
    rooms, winding = _winding(spec)
    want = []
    for cor in spec.corridors:
        path = corridor_path(cor, rooms)
        if cor.id in winding:
            pts = [p for line in winding_legs(cor, rooms) if line for p in line]
            it = iter(path)
            assert all(any(q == p for q in it) for p in pts)
            assert len(path) > len(corridor_route(cor, rooms).waypoints)
        elif cor.path:
            assert path == [tuple(p) for p in cor.path]
        else:
            assert path == list(corridor_route(cor, rooms).waypoints)
        want.append(len(path))
    svg = render_map_svg(spec, outline=_plain_outline(spec))
    got = [len(m.split()) for m in re.findall(r'<polyline (?:class="threshold" )?points="([^"]*)"', svg)]
    assert sorted(got) == sorted(want)


# --- The outline and EQ map on angled walls ----------------------------------------------

def _tunnel_ter(seed, overlap, along_x=True):
    """A winding tunnel's floor and walls, angled, far off the origin and read back from
    bytes (float32, as a built TER is): each segment's floor in three quads, a wall on each
    side of each quad, a wall across each end; along X, or along Y (an angled line nearly
    across X, whose pieces' ends can sort either way). ``overlap`` lays a second floor quad over part
    of one segment (as a corridor end lies over a room's floor), so the outline's union of
    pieces on one supporting line runs on angled lines. Returns the TER, the centreline, and
    the strip's sides."""
    hw = 8.0
    ox, oy = 1000.0, -700.0
    end = (ox + 260.0, oy) if along_x else (ox, oy + 260.0)
    line = wind_leg((ox, oy), end, along_x, hw, 30.0, ROUGH, f"readers{seed}")
    left, right = _mitred(line, hw)
    ter = TerFile(name="tunnel")
    ter.materials.append(Material(index=0, name="floor"))

    def quad(*corners):
        k = len(ter.vertices)
        ter.vertices.extend(Vertex(float(x), float(y), float(z)) for x, y, z in corners)
        ter.polygons += [Polygon(k, k + 1, k + 2), Polygon(k, k + 2, k + 3)]

    def at(side, i, f):
        return side[i] + (side[i + 1] - side[i]) * f

    for i in range(len(line) - 1):
        for s in range(3):
            l0, l1 = at(left, i, s / 3), at(left, i, (s + 1) / 3)
            r0, r1 = at(right, i, s / 3), at(right, i, (s + 1) / 3)
            quad((*r0, 0), (*r1, 0), (*l1, 0), (*l0, 0))
            quad((*l0, 0), (*l1, 0), (*l1, 12), (*l0, 12))
            quad((*r1, 0), (*r0, 0), (*r0, 12), (*r1, 12))
    if overlap:
        i = 1
        p, q = np.asarray(line[i]), np.asarray(line[i + 1])
        d = (q - p) / np.linalg.norm(q - p)
        n = np.array([-d[1], d[0]])
        m = p + (q - p) * 0.7
        quad((*right[i], 0), (*(m - n * hw), 0), (*(m + n * hw), 0), (*left[i], 0))
    for a, b in ((right[0], left[0]), (left[-1], right[-1])):
        quad((*a, 0), (*b, 0), (*b, 12), (*a, 12))
    return TerFile.from_bytes(ter.to_bytes(), name="tunnel"), line, left, right


def _seg_dist(p, a, b):
    p, a, b = (np.asarray(v, float)[:2] for v in (p, a, b))
    ab = b - a
    t = min(1.0, max(0.0, float((p - a) @ ab) / float(ab @ ab)))
    return float(np.linalg.norm(p - a - t * ab))


@pytest.mark.parametrize("along_x", [True, False])
@pytest.mark.parametrize("overlap", [False, True])
@pytest.mark.parametrize("seed", range(10))
def test_outline_and_eq_map_trace_angled_walls(seed, overlap, along_x):
    """The tunnel's walls come out as walls, each once: as long as the strip's sides and
    ends, every point of a side on one, and the EQ map draws the same angled lines."""
    ter, line, left, right = _tunnel_ter(seed, overlap, along_x)
    start = (line[0][0] + 3.0, line[0][1]) if along_x else (line[0][0], line[0][1] + 3.0)
    out = extract_outline(ter, (*start, 0.25))
    walls = [p for p in out.polylines if p.kind == "wall"]
    sides = sum(float(np.linalg.norm(s[i + 1] - s[i])) for s in (left, right) for i in range(len(s) - 1))
    want = sides + 2 * 2 * 8.0
    assert sum(p.length for p in walls) == pytest.approx(want, abs=0.01)
    assert sum(p.length for p in out.polylines if p.kind == "ledge") < 0.01
    segs = [(p, q) for pl in walls for p, q in zip(pl.points, pl.points[1:])]
    assert any(abs(p[0] - q[0]) > 0.5 and abs(p[1] - q[1]) > 0.5 for p, q in segs), "no angled wall"
    for side in (left, right):
        for i in range(len(side) - 1):
            for f in (0.1, 0.5, 0.9):
                pt = side[i] + (side[i + 1] - side[i]) * f
                assert min(_seg_dist(pt, p, q) for p, q in segs) < 0.01
    mf = build_map_file(out, ZoneSpec(name="tunnel"), "tunnel")
    lines = [ln for layer in mf.layers for ln in layer.lines]
    length = sum(math.hypot(ln.x2 - ln.x1, ln.y2 - ln.y1) for ln in lines)
    assert length == pytest.approx(sum(p.length for p in out.polylines), abs=0.01)
