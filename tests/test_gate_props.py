"""The room gate learns placed models (room-decor spec task 5, Requirement 2).

P1: hand-built room cases fail the walk gate, named, for each failure: a
Footprint cutting reached floor off from the entrance, a door's way narrowed
below the clear width, a POI not reached. The gate reads the models' own
triangles, placed by ZON objects; nothing tells it a shape. Two of the models
are open shells wound any way, as stock models are: nothing here is closed.

P2: with no placed model in the room graph the gate's answer and report are
today's, on dungeon, city and outdoor-dungeon builds (an outdoor dungeon's
trees stand outside the room graph).
"""

from __future__ import annotations

import functools
import math
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.footprints import CLEAR_WIDTH, HEAD_HEIGHT, Placed
from analyzer.traverse import _door_strips, validate
from core.pfs import PfsArchive
from core.ter import MAGIC_MODEL, Material, Polygon, TerFile, Vertex
from core.zon import ZonFile, ZonObject
from generators.builder import ZoneBuilder
from generators.pipeline import _traversal_report
from tests.pbt_helpers import scaled

# ---------------------------------------------------------------------------
# Hand-built models
# ---------------------------------------------------------------------------


def _model(quads, name, flips=0):
    """A model of quads (4 corners each, two triangles), every triangle
    collidable. Bit k of ``flips`` turns triangle k over."""
    verts, polys = [], []
    for q in quads:
        base = len(verts)
        verts += [Vertex(x=x, y=y, z=z, nx=0.0, ny=0.0, nz=1.0, u=0.0, v=0.0) for x, y, z in q]
        for a, b, c in ((0, 1, 2), (0, 2, 3)):
            if flips >> len(polys) & 1:
                b, c = c, b
            polys.append(Polygon(base + a, base + b, base + c, material=0, flags=0))
    mat = Material(index=0, name="props_test", shader="Opaque_MaxCB1.fx")
    return TerFile(name=name, magic=MAGIC_MODEL, version=2, materials=[mat],
                   vertices=verts, polygons=polys)


def crate(width, depth=3.0, height=6.0, flips=0):
    """A closed box, ``width`` along x, from y = 0 to ``depth``, wound outward."""
    x0, x1, y0, y1, z0, z1 = -width / 2, width / 2, 0.0, depth, 0.0, height
    c = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return _model([[c[i] for i in f] for f in faces], "props_crate.mod", flips)


def fence(length, height=10.0, flips=0b10):
    """One open wall of no thickness along x at y = 0: a single quad, its two
    triangles wound opposite ways (by default), as a stock mesh may be."""
    h = length / 2
    return _model([[(-h, 0, -1), (h, 0, -1), (h, 0, height), (-h, 0, height)]],
                  "props_fence.mod", flips)


def pen(half, height=10.0, flips=0b10100101):
    """Four open walls round the origin, no floor, no roof, wound every which
    way: an open shell like stock's."""
    h = half
    corners = [(-h, -h), (h, -h), (h, h), (-h, h)]
    quads = []
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        quads.append([(ax, ay, -1), (bx, by, -1), (bx, by, height), (ax, ay, height)])
    return _model(quads, "props_pen.mod", flips)


# ---------------------------------------------------------------------------
# The room build: four rooms, two shaped (Throats), two holding POIs
# ---------------------------------------------------------------------------

FIELDS = dict(zone_type="dungeon", room_count=4, elevation=False)
SEED = 3


@functools.lru_cache(maxsize=None)
def _built():
    spec = plan_to_spec(ZonePlan(name="gate_props", **FIELDS).validate(), seed=SEED)
    out = Path(tempfile.mkdtemp(prefix="gate_props_"))
    result = ZoneBuilder(spec).build(output_dir=out, write_glb=False)
    return spec, result.eqg_path


@pytest.fixture(scope="module")
def built():
    spec, eqg = _built()
    yield spec, eqg


def _room(spec, rid):
    return next(r for r in spec.rooms if r.id == rid)


def _door(spec, rid):
    """(side, c0, c1, door-middle point, yaw facing into the room) of the
    room's first door; a model's +y is into the room at that yaw."""
    room = _room(spec, rid)
    side, c0, c1 = _door_strips(room, spec)[0]
    (x0, y0, z0), (x1, y1, _) = room.bounds
    mid = (c0 + c1) / 2
    at = {"S": (mid, y0), "N": (mid, y1), "W": (x0, mid), "E": (x1, mid)}[side]
    yaw = {"S": 0.0, "N": math.pi, "W": -math.pi / 2, "E": math.pi / 2}[side]
    return side, c0, c1, (at[0], at[1], z0), yaw


def _inward(point, yaw, depth):
    x, y, z = point
    return x - math.sin(yaw) * depth, y + math.cos(yaw) * depth, z


def _failures(spec, eqg, placed):
    rep = validate(eqg, spec=spec, check_corridors=True, placed=placed)
    return rep, [o for o in rep.outlines if not o.ok]


def _kinds(fails):
    return sorted({o.reason.split(":")[0] for o in fails})


# The three hand-built cases, by name.

def _case(spec, name, flips):
    if name == "cut":
        # An open fence across the dead end's door, sealing it.
        side, c0, c1, at, yaw = _door(spec, "room_3")
        x, y, z = _inward(at, yaw, 2.0)
        return [Placed("fence_1", "props_fence.mod", fence(c1 - c0 + 8.0, flips=flips),
                       x, y, z, yaw)]
    if name == "narrow":
        # A closed crate in the dead end's doorway, 6.5 u clear each side.
        side, c0, c1, at, yaw = _door(spec, "room_3")
        return [Placed("crate_1", "props_crate.mod", crate(c1 - c0 - 13.0, flips=flips),
                       *at, yaw)]
    if name == "poi":
        # An open pen round the boss POI.
        poi = _room(spec, "room_2").pois[0]
        return [Placed("pen_1", "props_pen.mod", pen(6.0, flips=flips),
                       poi.x, poi.y, poi.z, 0.3)]
    raise ValueError(name)


# A fence sealing a door cuts the room off, so the room's POI and the door's
# clear width go with it: all three are named.
EXPECTED = {
    "cut": (["footprint_cut", "poi_unreached", "throat_narrow"], "fence_1", "room_3"),
    "narrow": (["throat_narrow"], "crate_1", "room_3"),
    "poi": (["poi_unreached"], "boss", "room_2"),
}


# ---------------------------------------------------------------------------
# P1: each failure, named
# ---------------------------------------------------------------------------

@given(name=st.sampled_from(sorted(EXPECTED)), flips=st.integers(0, 2 ** 12 - 1))
@example(name="cut", flips=0b10)             # an open fence, its halves wound apart
@example(name="narrow", flips=0)             # a closed crate, wound outward
@example(name="poi", flips=0b10100101)       # an open pen, wound every which way
@example(name="narrow", flips=2 ** 12 - 1)   # the crate turned inside out
@settings(max_examples=scaled(6), deadline=None)
def test_each_failure_named(name, flips):
    """However a model's triangles are wound, closed or not, each case fails
    as itself, naming the model (or POI) and its room."""
    spec, eqg = _built()
    _rep, fails = _failures(spec, eqg, _case(spec, name, flips))
    kinds, subject, where = EXPECTED[name]
    assert _kinds(fails) == kinds, [o.reason for o in fails]
    first = next(o for o in fails if o.reason.startswith(kinds[0]))
    assert subject in first.reason and first.room_id == where, first


def test_cut_judged_from_what_ships(built, tmp_path):
    """The pipeline's own gate call reads the ZON objects and models packed
    in the ``.eqg``: no ``placed`` passes in, so nothing takes the placer's
    word."""
    spec, eqg = built
    shipped = tmp_path / eqg.name
    shutil.copy(eqg, shipped)
    (p,) = _case(spec, "cut", 0b10)
    arc = PfsArchive.from_file(shipped)
    zon_name = next(f for f in arc.list_files() if f.lower().endswith(".zon"))
    zon = ZonFile.from_bytes(arc.get(zon_name))
    zon.models.append(p.model_name)
    zon.objects.append(ZonObject(p.name, len(zon.models) - 1, p.x, p.y, p.z, p.yaw))
    arc.add(p.model_name, p.model.to_bytes())
    arc.add(zon_name, zon.to_bytes())
    arc.write_file(shipped)

    report = _traversal_report(shipped, spec, None)
    assert not report.passed
    fails = [o for o in report.outlines if not o.ok]
    assert _kinds(fails) == EXPECTED["cut"][0]
    assert any("fence_1" in o.reason and o.room_id == "room_3" for o in fails)


def test_wide_enough_doorway_passes(built):
    """A crate leaving 8.5 u each side of the doorway narrows nothing."""
    spec, eqg = built
    side, c0, c1, at, yaw = _door(spec, "room_3")
    placed = [Placed("crate_1", "props_crate.mod", crate(c1 - c0 - 2 * (CLEAR_WIDTH + 0.5)),
                     *at, yaw)]
    rep, fails = _failures(spec, eqg, placed)
    assert not fails and rep.passed, [o.reason for o in fails]


def test_over_head_and_other_levels_pass(built):
    """The fence that cuts the dead end, hung over head height or sunk below
    the floor, blocks nothing: each Level is judged at its own floor."""
    spec, eqg = built
    (p,) = _case(spec, "cut", 0b10)
    for dz in (HEAD_HEIGHT + 1.5, -40.0):
        moved = Placed(p.name, p.model_name, p.model, p.x, p.y, p.z + dz, p.yaw)
        rep, fails = _failures(spec, eqg, [moved])
        assert not fails and rep.passed, (dz, [o.reason for o in fails])


def test_models_off_the_floor_space_pass(built):
    """Crates standing apart in a room's open floor, clear of its doors and
    POIs, pass: the gate fails only what a model changes."""
    spec, eqg = built
    room = _room(spec, "room_1")
    (x0, y0, z0), (x1, y1, _) = room.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    placed = [Placed(f"crate_{k}", "props_crate.mod", crate(3.0), cx + dx, cy + dy, z0, 0.0)
              for k, (dx, dy) in enumerate([(-6, -6), (6, 6), (-6, 6), (6, -6)])]
    rep, fails = _failures(spec, eqg, placed)
    assert not fails and rep.passed, [o.reason for o in fails]


# ---------------------------------------------------------------------------
# P2: no placed models, today's answer
# ---------------------------------------------------------------------------

P2_BUILDS = {
    "dungeon": (dict(zone_type="dungeon", room_count=8, layout="classic"), 7),
    "city": (dict(zone_type="city", room_count=7), 5),
    "outdoor_dungeon": (dict(zone_type="outdoor_dungeon", room_count=5, locks=1,
                             layout="classic"), 3),
}


def _report_key(rep):
    return (rep.summary(), [(o.room_id, o.ok, o.reason) for o in rep.outlines],
            [(c.corridor_id, c.connected, c.reason) for c in rep.corridors], rep.conflicts)


@pytest.mark.parametrize("label", sorted(P2_BUILDS))
def test_no_models_in_the_room_graph_same_report(label, tmp_path):
    """The gate on a build's own ``.eqg`` (whatever its ZON places) gives
    exactly the report it gives with no placed models at all."""
    fields, seed = P2_BUILDS[label]
    spec = plan_to_spec(ZonePlan(name=f"p2_{label}", **fields).validate(), seed=seed)
    eqg = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False).eqg_path
    shipped = validate(eqg, spec=spec, check_corridors=True)
    none = validate(eqg, spec=spec, check_corridors=True, placed=[])
    assert _report_key(shipped) == _report_key(none)
    assert shipped.passed and shipped.corridors_passed
