"""Winding routes task 2 (Requirement 3; design "Mesh"): a corridor with a ``path`` is built as
one winding strip from opening to opening, flat over both run-outs, its rise spread over the
rest, every floor piece rising at most ``MAX_SEG_RISE``; the traversability gate passes.
"""

import functools
import math

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.geometry import MAX_SEG_RISE, MeshBuilder, _ensure_materials
from generators.layout import ENTRY_MAX
from generators.routing import strip_corners

#: (theme, seed, rooms, verticality): 10 cave and 5 warren graph builds, 8-30 rooms, each verticality.
BUILDS = [("cave", s, r, v) for s, (r, v) in enumerate(
    [(8, "flat"), (12, "moderate"), (16, "dramatic"), (20, "flat"), (25, "moderate"),
     (30, "dramatic"), (10, "flat"), (14, "moderate"), (22, "dramatic"), (28, "flat")])]
BUILDS += [("warren", 100 + s, r, v) for s, (r, v) in enumerate(
    [(8, "flat"), (14, "moderate"), (20, "dramatic"), (26, "flat"), (30, "moderate")])]
IDS = [f"{t}{s}-{r}-{v}" for t, s, r, v in BUILDS]


@functools.lru_cache(maxsize=None)
def _spec(theme, seed, rooms, verticality):
    from generators.pipeline import _with_decor
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "dungeon_theme": theme, "layout": "graph",
                                   "room_count": rooms, "verticality": verticality}, [])
    plan.name = f"wrm_{theme}{seed}"
    return _with_decor(plan_to_spec(plan, seed=seed, warnings=[]))


def _floor_tris(spec, cor):
    """The floor triangles ``add_corridor`` lays for ``cor`` alone: (3 x (x, y, z))."""
    _ensure_materials(spec)
    mb = MeshBuilder()
    mb.add_corridor(cor, spec)
    out = []
    for p in mb.polygons:
        vs = [mb.vertices[i] for i in (p.v1, p.v2, p.v3)]
        if all(v.nz == 1 for v in vs):
            out.append([(v.x, v.y, v.z) for v in vs])
    return out


@pytest.mark.parametrize("case", BUILDS, ids=IDS)
def test_path_strip_pieces_and_ends(case):
    """Every path corridor's floor is one strip: no piece rises more than MAX_SEG_RISE, its
    ends are the straight route's square doorway ends at the rooms' heights, and nothing of it
    lies outside the path's strip (no straight leg, no bend square)."""
    spec = _spec(*case)
    for cor in spec.corridors:
        if not cor.path:
            continue
        tris = _floor_tris(spec, cor)
        assert tris, cor.id
        for tri in tris:
            zs = [p[2] for p in tri]
            assert max(zs) - min(zs) <= MAX_SEG_RISE + 1e-6, (cor.id, tri)
        hw = cor.width / 2
        # Each end's two corners: square across the line, or for an angled end (random
        # placement task 10) cut along the wall it leaves, as ``strip_corners`` lays them.
        corners = strip_corners(cor.path, hw)
        for pair, z in ((corners[0], cor.from_z), (corners[-1], cor.to_z)):
            for x, y in pair:
                want = (x, y, z)
                assert any(math.dist(p, want) < 1e-6 for tri in tris for p in tri), (cor.id, want)
        lo, hi = min(cor.from_z, cor.to_z), max(cor.from_z, cor.to_z)
        for tri in tris:
            for x, y, z in tri:
                assert lo - 1e-6 <= z <= hi + 1e-6
                near = min(_seg_dist((x, y), p, q) for p, q in zip(cor.path, cor.path[1:]))
                # A mitre at a 60 degree turn; an angled end's cap, up to ENTRY_MAX off
                # square, and the mitres of its entry line's turns (random placement task 10).
                most = max(30.0, ENTRY_MAX if cor.entry else 0.0,
                           max(_turns(cor.path)) / 2 if cor.entry else 0.0)
                assert near <= hw / math.cos(math.radians(most)) + 1e-6, (cor.id, x, y)


def _turns(line):
    """The turn (degrees) at each interior vertex of ``line``."""
    out = []
    for a, b, c in zip(line, line[1:], line[2:]):
        u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        out.append(abs(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))))
    return out or [0.0]


def _seg_dist(pt, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(pt[0] - a[0] - t * dx, pt[1] - a[1] - t * dy)


@pytest.mark.slow
@pytest.mark.parametrize("case", BUILDS, ids=IDS)
def test_builds_pass_the_gate(case, tmp_path):
    """The built zone passes the traversability gate with the corridor checks, as the themed
    navigability sweep runs it."""
    from analyzer.traverse import validate
    from generators.builder import ZoneBuilder
    spec = _spec(*case)
    res = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    report = validate(res.eqg_path, spec=spec, check_corridors=True)
    bad = [f"{r.room_id}: {r.reason or 'unreachable'}" for r in report.rooms if not r.reachable]
    bad += [f"{o.room_id}: {o.reason}" for o in report.outlines if not o.ok]
    bad += [f"corridor {c.corridor_id}: {c.reason}" for c in report.corridors if not c.connected]
    bad += [f"conflict {c}" for c in report.conflicts]
    assert report.passed and report.corridors_passed, bad


def test_most_builds_have_paths():
    """The builds above exercise the path mesh: most rough cave corridors carry a path (warrens,
    whose rooms sit closer, get fewer)."""
    rough = with_path = 0
    for case in BUILDS:
        if case[0] != "cave":
            continue
        for cor in _spec(*case).corridors:
            if cor.rough > 0 and cor.transition is None:
                rough += 1
                with_path += bool(cor.path)
    assert with_path >= 0.6 * rough, (with_path, rough)
