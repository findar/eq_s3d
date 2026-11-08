"""The gate learns Structures (wilderness POIs spec task 2, Requirement 2).

P1: hand-built zones holding Structures fail the walk gate, named, for each
of the four failures: a Footprint cutting reached ground off from Spawn, an
Enterable opening narrower than the clear width or lower than head height, an
Enterable interior not reached, a POI not reached. The gate reads the models'
own triangles, placed by ZON objects; nothing here tells it a shape.

P2: on tree-only zones the Footprint check gives ``trees_block``'s answer.

Structure meshes are built by hand here (closed boxes); task 3 builds the real
models.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.footprints import (
    CLEAR_WIDTH,
    HEAD_HEIGHT,
    POI,
    check_footprints,
    collidable_triangles,
    measure_opening,
    placed_from_zon,
)
from analyzer.traverse import AgentModel
from core.ter import FLAG_PASSABLE, MAGIC_MODEL, Material, Polygon, TerFile, Vertex
from core.zon import ZonFile, ZonObject
from generators.vegetation.placement import TreeInstance
from generators.wilderness import build as wb
from tests.pbt_helpers import scaled

# ---------------------------------------------------------------------------
# Hand-built models
# ---------------------------------------------------------------------------

#: Walls start this far under the ground (a skirt) and stand this tall.
SKIRT, WALL_TOP = 3.0, 12.0


def _box(lo, hi):
    """A closed box, wound outward: 8 corners, 12 triangles."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    c = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    tris = []
    for a, b, cc, d in quads:
        tris += [(a, b, cc), (a, cc, d)]
    return c, tris


def _model(boxes, name="site_test.mod", passable=()):
    """One model from boxes; the ``passable`` ones carry FLAG_PASSABLE."""
    verts, polys = [], []
    for k, (lo, hi) in enumerate(list(boxes) + list(passable)):
        c, tris = _box(lo, hi)
        base = len(verts)
        verts += [Vertex(x=x, y=y, z=z, nx=0.0, ny=0.0, nz=1.0, u=0.0, v=0.0) for x, y, z in c]
        flags = FLAG_PASSABLE if k >= len(boxes) else 0
        polys += [Polygon(base + a, base + b, base + cc, material=0, flags=flags) for a, b, cc in tris]
    mat = Material(index=0, name="site_test", shader="Opaque_MaxCB1.fx")
    return TerFile(name=name, magic=MAGIC_MODEL, version=2, materials=[mat],
                   vertices=verts, polygons=polys)


def hut(door=10.0, lintel=10.0, size=24.0, wall=1.0, roof=True):
    """A square hut, ``size`` across outside, walls ``wall`` thick, a door
    ``door`` wide in its +Y wall under a lintel at ``lintel``, and a passable
    thatch roof over head height. Floored by the ground (no floor of its own)."""
    h = size / 2
    lo, hi = -SKIRT, WALL_TOP
    boxes = [
        ((-h, -h, lo), (h, -h + wall, hi)),               # -Y wall
        ((-h, -h, lo), (-h + wall, h, hi)),               # -X wall
        ((h - wall, -h, lo), (h, h, hi)),                 # +X wall
        ((-h, h - wall, lo), (-door / 2, h, hi)),         # +Y wall, left of the door
        ((door / 2, h - wall, lo), (h, h, hi)),           # +Y wall, right of the door
    ]
    if door > 0 and lintel < hi:
        boxes.append(((-door / 2, h - wall, lintel), (door / 2, h, hi)))
    roof_box = [((-h - 2, -h - 2, hi), (h + 2, h + 2, hi + 1))] if roof else []
    return _model(boxes, "site_hut.mod", passable=roof_box)


def wall(length=60.0, thick=1.0):
    """A straight wall run along X, centred: not Enterable."""
    return _model([((-length / 2, -thick / 2, -SKIRT), (length / 2, thick / 2, WALL_TOP))],
                  "site_wall.mod")


# ---------------------------------------------------------------------------
# A hand-built zone: a real wilderness TER, Structures placed by a ZON
# ---------------------------------------------------------------------------

EDGES = {"N": "zoneline"}


@pytest.fixture(scope="module")
def zone():
    spec = plan_to_spec(ZonePlan(name="karana", zone_type="wilderness"), seed=5, edges=EDGES)
    spec.wilderness["trees"] = "none"
    ter = wb.build_wilderness_ter(spec, "ter_karana", 2)
    ground = wb._ground_raster(spec, ter, AgentModel())
    return spec, ter, ground


def _ground_z(ground, x, y):
    i, j = ground.index(x, y)
    return float(ground.z_at(np.array([i]), np.array([j]))[0])


def _zon(ground, items):
    """``items``: (name, model, x, y, yaw). Each stands on the ground."""
    zon = ZonFile(models=["TER_KARANA.TER"])
    models = {}
    for name, model, x, y, yaw in items:
        if model.name not in models:
            models[model.name] = model
            zon.models.append(model.name)
        zon.objects.append(ZonObject(name=name, model_id=zon.models.index(model.name),
                                     x=x, y=y, z=_ground_z(ground, x, y), yaw=yaw))
    return zon, models


def _check(zone, items, pois=()):
    """The Footprint check's report on a hand-built zone (the ground cached)."""
    spec, ter, ground = zone
    zon, models = _zon(ground, items)
    return check_footprints(ground, placed_from_zon(zon, models), pois)


def _gate(zone, items, pois=()):
    """The whole bowl gate's verdict on a hand-built zone."""
    spec, ter, ground = zone
    zon, models = _zon(ground, items)
    return wb.bowl_report(spec, ter, zon=zon, models=models, pois=pois).rooms[0]


def _site(zone, dx=90.0, dy=0.0):
    spec = zone[0]
    return spec.safe_point[0] + dx, spec.safe_point[1] + dy


def _pen(cx, cy, half=20.0, yaw=0.0):
    """Four separate wall runs closing a square pen round (cx, cy)."""
    items = []
    for k in range(4):
        a = yaw + k * math.pi / 2
        items.append((f"pen_{k}", wall(2 * half + 4), cx + half * math.cos(a),
                      cy + half * math.sin(a), a + math.pi / 2))
    return items


# ---------------------------------------------------------------------------
# P1: each failure fails, named
# ---------------------------------------------------------------------------

def _blocked_door(x, y):
    """A good hut whose door is walled across by a separate wall run."""
    return [("hut_0", hut(), x, y, 0.0), ("fence_0", wall(30.0), x, y + 12.0 + 2.5, 0.0)]


#: One pinned hand-built case per failure: (items at (x, y), POIs, the failure
#: the gate must name, and the subject it must name).
CASES = {
    "footprint_cut": (lambda x, y: _pen(x, y), lambda x, y: (), "pen_"),
    "opening_narrow": (lambda x, y: [("hut_0", hut(door=5.0), x, y, 0.4)], lambda x, y: (), "hut_0"),
    "opening_low": (lambda x, y: [("hut_0", hut(lintel=7.0), x, y, 0.4)], lambda x, y: (), "hut_0"),
    "interior_unreached": (_blocked_door, lambda x, y: (), "hut_0"),
    "poi_unreached": (lambda x, y: _pen(x, y),
                      lambda x, y: (POI("shrine altar", x, y), POI("lookout", x + 60, y)),
                      "shrine altar"),
}


def test_a_good_hut_with_a_poi_inside_passes_the_gate(zone):
    x, y = _site(zone)
    items, pois = [("hut_0", hut(), x, y, 0.3)], [POI("hut interior", x, y)]
    assert _check(zone, items, pois).passed
    room = _gate(zone, items, pois)
    assert room.reachable, room.reason


@pytest.mark.parametrize("kind", sorted(CASES))
def test_p1_the_gate_names_each_failure(zone, kind):
    make, make_pois, subject = CASES[kind]
    x, y = _site(zone)
    report = _check(zone, make(x, y), make_pois(x, y))
    named = [s for f in report.of(kind) for s in f.subjects]
    assert named and all(s.startswith(subject) for s in named), report.failures
    room = _gate(zone, make(x, y), make_pois(x, y))
    assert not room.reachable and f"{kind}: {subject}" in room.reason, room.reason


@given(yaw=st.floats(0.0, 2 * math.pi), half=st.floats(12.0, 30.0))
@example(yaw=0.0, half=20.0)
@example(yaw=math.pi / 4, half=20.0)
@settings(max_examples=scaled(6), deadline=None)
def test_p1_a_footprint_that_cuts_off_ground_fails(zone, yaw, half):
    x, y = _site(zone)
    items = _pen(x, y, half, yaw)
    report = _check(zone, items)
    cuts = report.of("footprint_cut")
    assert cuts and set(cuts[0].subjects) <= {n for n, *_ in items}
    assert not report.of("opening_narrow") and not report.of("opening_low")


@given(yaw=st.floats(0.0, 2 * math.pi), door=st.floats(0.0, CLEAR_WIDTH - 1.0))
@example(yaw=0.0, door=0.0)                 # no door at all
@example(yaw=0.0, door=CLEAR_WIDTH - 1.0)
@example(yaw=math.pi / 8, door=5.0)
@settings(max_examples=scaled(8), deadline=None)
def test_p1_a_narrow_opening_fails(zone, yaw, door):
    x, y = _site(zone)
    report = _check(zone, [("hut_0", hut(door=door), x, y, yaw)])
    assert [f.subjects for f in report.of("opening_narrow")] == [("hut_0",)]


@given(yaw=st.floats(0.0, 2 * math.pi), lintel=st.floats(AgentModel().player_height + 0.3,
                                                          HEAD_HEIGHT - 0.5))
@example(yaw=0.0, lintel=7.0)
@settings(max_examples=scaled(8), deadline=None)
def test_p1_a_low_opening_fails(zone, yaw, lintel):
    x, y = _site(zone)
    report = _check(zone, [("hut_0", hut(lintel=lintel), x, y, yaw)])
    assert [f.subjects for f in report.of("opening_low")] == [("hut_0",)]
    assert not report.of("opening_narrow")


def test_p1_an_unreached_interior_fails(zone):
    x, y = _site(zone)
    report = _check(zone, _blocked_door(x, y))
    assert [f.subjects for f in report.of("interior_unreached")] == [("hut_0",)]
    assert not report.of("opening_narrow") and not report.of("opening_low")


def test_p1_an_unreached_poi_fails(zone):
    x, y = _site(zone)
    report = _check(zone, _pen(x, y), [POI("shrine altar", x, y), POI("lookout", x + 60, y)])
    assert [f.subjects for f in report.of("poi_unreached")] == [("shrine altar",)]


# ---------------------------------------------------------------------------
# The raster: thin walls don't slip through, door gaps don't close up
# ---------------------------------------------------------------------------

@given(yaw=st.floats(0.0, 2 * math.pi), door=st.floats(CLEAR_WIDTH, 14.0),
       wall_t=st.floats(0.05, 2.0))
@example(yaw=0.0, door=CLEAR_WIDTH, wall_t=0.05)
@example(yaw=math.pi / 4, door=CLEAR_WIDTH, wall_t=0.05)
@example(yaw=0.3927, door=CLEAR_WIDTH, wall_t=1.0)
@settings(max_examples=scaled(30), deadline=None)
def test_an_opening_of_the_clear_width_passes_at_any_angle(yaw, door, wall_t):
    rot = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])
    local = collidable_triangles(hut(door=door, wall=wall_t)) @ rot.T
    op = measure_opening(local)
    assert op.enterable and not op.narrow and not op.low


@given(yaw=st.floats(0.0, 2 * math.pi), wall_t=st.floats(0.0, 0.3))
@example(yaw=math.pi / 4, wall_t=0.0)       # a wall of no thickness, diagonal
@example(yaw=0.1, wall_t=0.0)
@settings(max_examples=scaled(15), deadline=None)
def test_a_thin_closed_hut_never_lets_the_gate_in(yaw, wall_t):
    rot = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])
    local = collidable_triangles(hut(door=0.0, wall=wall_t)) @ rot.T
    op = measure_opening(local)
    assert op.enterable and op.narrow


def test_solids_and_fences_are_not_enterable():
    tower = _model([((-8, -8, -SKIRT), (8, 8, 40.0))], "site_tower.mod")
    assert not measure_opening(collidable_triangles(tower)).enterable
    assert not measure_opening(collidable_triangles(wall())).enterable


# ---------------------------------------------------------------------------
# P2: a trunk is a Footprint; tree-only zones get trees_block's answer
# ---------------------------------------------------------------------------

def _tree_spec(seed, level, edges):
    spec = plan_to_spec(ZonePlan(name="karana", zone_type="wilderness"), seed=seed, edges=edges)
    spec.wilderness["trees"] = level
    return spec


@pytest.mark.parametrize("seed, level, edges", [
    (5, "dense", {"N": "zoneline"}),
    (2275961, "dense", {}),
    (424242, "normal", {"W": "zoneline", "E": "zoneline"}),
    (31337, "sparse", {"N": "zoneline", "E": "river"}),
])
def test_p2_trees_footprints_agree_with_trees_block_on_builds(seed, level, edges):
    spec = _tree_spec(seed, level, edges)
    spec.sites = "none"  # P2 is about tree-only zones
    ter = wb.build_wilderness_ter(spec, "ter_karana", 2)
    veg = wb.vegetation_for(spec, ter)
    zon, models = wb._gate_zon(spec, ter)
    assert len(zon.objects) == len(veg.placement.instances) > 0
    disc = wb.trees_block(spec, ter, veg.placement.instances)
    footprints = wb.structure_failures(spec, ter, zon, models)
    assert (disc is None) == (not footprints), (disc, footprints)


def _ring_zon(spec, ground, n, radius, species="broadleaf", scale=1.0):
    """``n`` trees evenly round Spawn, standing on the ground, as instances
    and as the ZON the builder writes for them."""
    from generators.vegetation.kit import load_vegetation_kit
    from generators.vegetation.models import model_name, tree_model

    sx, sy = spec.safe_point[0], spec.safe_point[1]
    kit = load_vegetation_kit("plains_grassland")
    sp = kit.species[species]
    trees = []
    for k in range(n):
        a = 2 * math.pi * k / n
        x, y = sx + radius * math.cos(a), sy + radius * math.sin(a)
        trees.append(TreeInstance(species, x, y, _ground_z(ground, x, y), a,
                                  scale, sp.trunk_radius * scale))
    fname = model_name(sp)
    zon = ZonFile(models=["TER_KARANA.TER", fname])
    zon.objects = [ZonObject(name=f"veg_{i:04d}", model_id=1, x=t.x, y=t.y, z=t.z,
                             yaw=t.yaw, scale=t.scale) for i, t in enumerate(trees)]
    return trees, zon, {fname: tree_model(sp, 1)}


# A ring of 200 u round Spawn: n >= 180 trunks (spacing <= 7 u) close it under
# either check; n <= 90 (spacing >= 14 u) leaves gaps both see open.
@given(n=st.one_of(st.integers(180, 260), st.integers(30, 90)),
       radius=st.floats(150.0, 220.0))
@example(n=240, radius=200.0)
@example(n=90, radius=200.0)
@settings(max_examples=scaled(4), deadline=None)
def test_p2_trees_rings_agree_with_trees_block(zone, n, radius):
    spec, ter, ground = zone
    n = int(n * radius / 200.0) or 1      # keep the spacing band whatever the radius
    trees, zon, models = _ring_zon(spec, ground, n, radius)
    disc = wb.trees_block(spec, ter, trees)
    footprints = wb.structure_failures(spec, ter, zon, models)
    assert (disc is None) == (not footprints), (n, radius, disc, footprints)
    if footprints:
        assert footprints[0].startswith("tree trunks cut off playable cell")
