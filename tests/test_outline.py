"""Room walls task 3 (Requirements 2 and 4; design W1, W2, W5, W6, W9): Outlines and
their meshes, with no layout producing one yet.

The properties draw Outlines over any Box and door set. The meshes go through the
real walk surface and the gate's own check (task 2), between two rooms and a
corridor as a build would have them.
"""

import math
import random

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from analyzer.traverse import AgentModel, build_walk_surface, check_outline
from generators.geometry import _ensure_materials, build_mesh, room_doors
from generators.outline import COMPLEXES, EDGE_MAX, SHAPES, _fans_sound, draw_outline
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()
BOX_SIDE = st.floats(48.0, 200.0)
CELL = {"voronoi": 24.0, "grid": 24.0, "facet": 0.0}
WOBBLE = {"voronoi": 8.0, "grid": 0.0, "facet": 0.0}
ROOM_POLYGON_CAP = 3000     # task 3 measured the biggest human room: see the commit


def _doors(w, d, picks):
    """Doors on a Box of size ``w`` x ``d`` centred on the origin, 18 u wide, no two
    on one side."""
    doors = {}
    for side, t in picks:
        span = (w if side in "NS" else d) - 18.0
        lo = -span / 2 + span * t - 9.0
        doors[side] = (side, lo, lo + 18.0)
    return sorted(doors.values())


@settings(max_examples=60, deadline=None)
@given(w=BOX_SIDE, d=BOX_SIDE, complex=st.sampled_from(COMPLEXES), shape=st.sampled_from(SHAPES),
       fill=st.floats(0.65, 0.98), seed=st.integers(0, 10 ** 6),
       picks=st.lists(st.tuples(st.sampled_from("NSEW"), st.floats(0.0, 1.0)), max_size=4))
def test_w1_outline_is_inside_connected_and_reaches_every_door(w, d, complex, shape, fill, seed, picks):
    box = (-w / 2, -d / 2, w / 2, d / 2)
    doors = _doors(w, d, picks)
    o = draw_outline(box, doors, [], complex=complex, cell_size=CELL[complex], fill=fill,
                     shape=shape, rng=random.Random(seed), wobble=WOBBLE[complex])
    pts = np.array(o.verts)
    assert pts[:, 0].min() >= box[0] - 1e-3 and pts[:, 0].max() <= box[2] + 1e-3
    assert pts[:, 1].min() >= box[1] - 1e-3 and pts[:, 1].max() <= box[3] + 1e-3
    assert o.contains(np.array([[0.0, 0.0]]))[0], "the centre is floor"

    # Connected across shared edges.
    owners = {}
    for k, c in enumerate(o.cells):
        for a, b in zip(c, c[1:] + c[:1]):
            owners.setdefault((min(a, b), max(a, b)), []).append(k)
    seen, stack = {0}, [0]
    links = {k: set() for k in range(len(o.cells))}
    for own in owners.values():
        for a in own:
            links[a].update(own)
    while stack:
        for n in links[stack.pop()]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    assert len(seen) == len(o.cells), "one connected floor"

    # Every door's strip on its wall is floor, right across.
    planes = {"S": box[1], "N": box[3], "W": box[0], "E": box[2]}
    for side, c0, c1 in doors:
        at = np.linspace(c0 + 0.5, c1 - 0.5, 7)
        inset = 0.5 if side in "SW" else -0.5
        probe = (np.c_[at, np.full(7, planes[side] + inset)] if side in "NS"
                 else np.c_[np.full(7, planes[side] + inset), at])
        assert o.contains(probe).all(), (side, c0, c1)

    if complex != "facet":     # a facet room is its middle polygon, whatever that holds
        assert o.fill(box) >= fill - 0.12, "doors only add floor; wandering walls take a little"
    assert o.fill(box) >= 0.45
    assert len(o.wall_loops()) == 1, "one wall round one floor, no pinholes"
    for c in o.cells:
        assert _fans_sound(o.verts, c), "no Cell's fan folds over"


@settings(max_examples=25, deadline=None)
@given(w=BOX_SIDE, d=BOX_SIDE, complex=st.sampled_from(COMPLEXES), shape=st.sampled_from(SHAPES),
       seed=st.integers(0, 10 ** 6))
def test_w2_same_inputs_same_outline(w, d, complex, shape, seed):
    box = (-w / 2, -d / 2, w / 2, d / 2)
    kw = dict(complex=complex, cell_size=CELL[complex], fill=0.85, shape=shape, wobble=WOBBLE[complex])
    assert (draw_outline(box, [("E", -9.0, 9.0)], [], rng=random.Random(seed), **kw)
            == draw_outline(box, [("E", -9.0, 9.0)], [], rng=random.Random(seed), **kw))


@pytest.mark.parametrize("shape", ["cut", "blob"])
def test_rounded_shapes_lose_their_corners_first(shape):
    box = (-60.0, -60.0, 60.0, 60.0)
    o = draw_outline(box, [], [], complex="grid", cell_size=24.0, fill=0.8, shape=shape,
                     rng=random.Random(1))
    corners = np.array([[-55.0, -55.0], [55.0, 55.0], [-55.0, 55.0], [55.0, -55.0]])
    assert not o.contains(corners).any()


def test_a_cut_leaving_a_piece_with_no_area_keeps_the_walls_closed():
    """A Throat edge running through a Cell's corner left a zero-area piece (a hewn
    room, found drawing samples), whose edges read as walls and broke the loop."""
    box = (-60.0, -45.0, 60.0, 45.0)
    o = draw_outline(box, [("E", -20.0, -2.0), ("N", 15.0, 33.0)], [], complex="voronoi",
                     cell_size=48.0, relax=3, fill=0.85, shape="blob", rng=random.Random(13))
    assert o.wall_loops()


def _spec(complex, shape, seed, doors_at=(0.0,), width=100.0, depth=100.0, height=40.0):
    """Room a (shaped), with a corridor east to room b for each offset in ``doors_at``."""
    a = RoomSpec("a", 0.0, 0.0, width=width, depth=depth, height=height, open_walls=["E"])
    spec = ZoneSpec(name="o", zone_type="dungeon", safe_point=(0.0, 0.0, 1.0))
    spec.rooms = [a]
    for k, y in enumerate(doors_at):
        b = RoomSpec(f"b{k}", width / 2 + 150.0, y, width=100.0, depth=30.0, height=height,
                     open_walls=["W"])
        spec.rooms.append(b)
        spec.corridors.append(CorridorSpec(f"c{k}", width / 2, y, width / 2 + 100.0, y, width=18.0,
                                           height=height - 10.0, from_room="a", to_room=b.id))
    _ensure_materials(spec)
    box = (-width / 2, -depth / 2, width / 2, depth / 2)
    a.outline = draw_outline(box, room_doors(a, spec), [], complex=complex, cell_size=CELL[complex],
                             fill=0.8, shape=shape, rng=random.Random(seed), wobble=WOBBLE[complex])
    return spec


@pytest.mark.parametrize("complex", COMPLEXES)
@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_w5_w6_built_room_passes_the_gate(complex, shape, seed):
    """Closed apart from its doors, doors flush with the corridor, all walkable."""
    spec = _spec(complex, shape, seed, doors_at=(-25.0, 25.0))
    surf = build_walk_surface(build_mesh(spec).to_ter("o"), AGENT)
    v = check_outline(surf, spec.rooms[0], spec, AGENT)
    assert v.ok, v.reason
    from analyzer.traverse import corridor_continuity, flood_reachable, seed_face_for
    assert all(c.connected for c in corridor_continuity(surf, spec, AGENT))
    reached = flood_reachable(surf, seed_face_for(surf, spec.safe_point))
    assert any(surf.centroids[f, 0] > 100 for f in reached), "the far room is walked to"


@pytest.mark.parametrize("complex", COMPLEXES)
def test_faces_look_inward(complex):
    """Every wall's normal points at floor, every floor up, every ceiling down."""
    spec = _spec(complex, "blob", 4)
    mb = build_mesh(spec)
    room = spec.rooms[0]
    v = mb.vertices
    (x0, y0, z0), (x1, y1, z1) = room.bounds
    for p in mb.polygons:
        tri = [v[p.v1], v[p.v2], v[p.v3]]
        if max(t.x for t in tri) > x1 + 0.01:
            continue
        a, b, c = (np.array([t.x, t.y, t.z]) for t in tri)
        n = np.cross(b - a, c - a)
        assert np.dot(n, [tri[0].nx, tri[0].ny, tri[0].nz]) > 0, "winding matches the normal"


def _wall_faces(spec):
    mb = build_mesh(spec)
    (x0, y0, z0), (x1, y1, z1) = spec.rooms[0].bounds
    return mb, [p for p in mb.polygons
                if abs(mb.vertices[p.v1].nz) < 0.5
                and max(mb.vertices[i].x for i in (p.v1, p.v2, p.v3)) <= x1 + 0.01]


def test_median_edge_is_in_the_era_band():
    spec = _spec("voronoi", "blob", 5)
    mb, walls = _wall_faces(spec)
    edges = []
    for p in walls:
        pts = [np.array([mb.vertices[i].x, mb.vertices[i].y, mb.vertices[i].z]) for i in (p.v1, p.v2, p.v3)]
        edges += [np.linalg.norm(pts[k] - pts[(k + 1) % 3]) for k in range(3)]
    assert 5.0 <= np.median(edges) <= EDGE_MAX + 1, np.median(edges)


def test_polygon_cap_holds_for_a_big_room():
    """The cap at a measured margin: the biggest human room, finest Cells, tallest."""
    spec = _spec("voronoi", "blob", 6, width=120.0, depth=120.0, height=60.0)
    assert len(build_mesh(spec).polygons) <= ROOM_POLYGON_CAP


@pytest.mark.parametrize("complex", COMPLEXES)
def test_w9_wall_texture_runs_on_round_a_bend(complex):
    """At each wall vertex the two walls meeting there agree on U (and on V)."""
    spec = _spec(complex, "blob", 7)
    mb, walls = _wall_faces(spec)
    seen = {}
    for p in walls:
        for i in (p.v1, p.v2, p.v3):
            v = mb.vertices[i]
            key = (round(v.x, 2), round(v.y, 2), round(v.z, 2))
            seen.setdefault(key, set()).add(round(v.u, 3))
    # The whole run joins except where a loop closes: one seam per loop.
    forked = sum(len(u) > 1 for u in seen.values())
    loops = len(spec.rooms[0].outline.wall_loops())
    rows = math.ceil(40.0 / 14.0)
    assert forked <= loops * (rows + 1), (forked, loops)


def test_a_slot_stays_floor_and_its_ceiling_stays_open():
    box = (-60.0, -60.0, 60.0, 60.0)
    slot = (30.0, -40.0, 50.0, -20.0)
    o = draw_outline(box, [], [slot], complex="voronoi", cell_size=30.0, fill=0.75, shape="blob",
                     rng=random.Random(8))
    probe = np.array([[31.0, -39.0], [49.0, -21.0], [40.0, -30.0]])
    assert o.contains(probe).all()
    assert slot in o.throats


def test_a_wandering_wall_stays_out_of_every_throat():
    """Step 9 found one on a rough room with doors N and S: an edge between two moved vertices
    cut across a Throat, a retry in a real build."""
    from generators.outline import _segment_enters
    box = (-60.0, -59.4, 60.0, 59.4)
    for seed in range(60):
        o = draw_outline(box, [("N", 4.0, 22.0), ("S", 4.0, 22.0)], [], complex="voronoi", cell_size=24.0, fill=0.72,
                         shape="ell", rng=random.Random(seed), wobble=7.8)
        for loop in o.wall_loops():
            pts = [o.verts[i] for i in loop]
            for a, b in zip(pts, pts[1:] + pts[:1]):
                for t in o.throats:
                    assert not _segment_enters(a, b, t, inset=0.5), (seed, a, b, t)
