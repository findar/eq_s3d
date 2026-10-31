"""
tests/test_properties_mapgeom.py
--------------------------------
Property tests for the outline extractor and depth bands
(``generators/mapgeom.py``) on synthetic slab worlds, where the true outline is
known by construction.

Design reference: ``.kiro/specs/zone-generator-m2-true-layout-artifacts/design.md``,
"Correctness Properties" 2-7 and "Testing Strategy". The box-build examples of
Properties 1-3 are task 4.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from analyzer.traverse import AgentModel, build_walk_surface, flood_reachable, seed_face_for
from core.ter import Polygon, TerFile, Vertex
from generators.mapgeom import (
    EmptyFloorRegion,
    FloorSet,
    MAX_BANDS,
    depth_bands,
    extract_outline,
    floor_faces,
    outline_summary,
)
from tests.pbt_helpers import (
    floor_boundary_samples,
    on_floor_boundary,
    reference_bands,
    scaled,
)
from tests.strategies import slab_worlds, stacked_worlds


def _synthetic_settings(n: int = 100) -> settings:
    return settings(
        max_examples=scaled(n),
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    )


# ---------------------------------------------------------------------------
# Shared oracle plumbing
# ---------------------------------------------------------------------------

def _region(world, reachable_only: bool = True) -> np.ndarray:
    """The Floor_Region by its definition: signed-normal Floor_Faces, cut to
    the validator's reachable set from the safe point when reachable-only."""
    floor = floor_faces(world.ter)
    if not reachable_only:
        return floor
    surf = build_walk_surface(world.ter, AgentModel())
    reach = np.zeros(len(floor), bool)
    reach[list(flood_reachable(surf, seed_face_for(surf, world.safe_point)))] = True
    return floor & reach


def _segments(outline) -> np.ndarray:
    segs = [(p, q) for pl in outline.polylines for p, q in zip(pl.points, pl.points[1:])]
    return np.array(segs, dtype=float).reshape(-1, 2, 3)


def _dist_to_segments(pts: np.ndarray, segs: np.ndarray) -> np.ndarray:
    """Min 3D distance from each point to any segment."""
    if len(segs) == 0:
        return np.full(len(pts), np.inf)
    A, B = segs[:, 0], segs[:, 1]
    AB = B - A
    L2 = np.maximum(np.einsum("ij,ij->i", AB, AB), 1e-18)
    out = np.empty(len(pts))
    for s in range(0, len(pts), 256):
        q = pts[s:s + 256, None, :]
        t = np.clip(np.einsum("nsk,sk->ns", q - A, AB) / L2, 0.0, 1.0)
        d = np.linalg.norm(A + t[..., None] * AB - q, axis=2)
        out[s:s + 256] = d.min(axis=1)
    return out


def _segment_samples(outline, spacing: float = 1.0) -> np.ndarray:
    pts = []
    for pl in outline.polylines:
        for p, q in zip(pl.points, pl.points[1:]):
            p, q = np.array(p), np.array(q)
            n = max(1, int(math.ceil(np.linalg.norm(q - p) / spacing)))
            for k in range(n + 1):
                pts.append(p + (q - p) * (k / n))
    return np.array(pts, dtype=float).reshape(-1, 3)


def _covered_fraction(world, region, outline) -> float:
    pts, w, boundary = floor_boundary_samples(world.ter, region, 0.5)
    if not boundary.any():
        return 1.0
    near = _dist_to_segments(pts[boundary], _segments(outline)) <= 0.05
    return float(w[boundary][near].sum() / w[boundary].sum())


# ---------------------------------------------------------------------------
# Property 2: fidelity
# ---------------------------------------------------------------------------

@_synthetic_settings()
@given(world=slab_worlds())
def test_outline_fidelity(world):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 2: Outline
    fidelity — sound and clear of doorways (umbrella P22).

    Synthetic part: every point of every emitted segment lies within 0.05 u of
    the Floor_Boundary, checked by its definition. (The doorway clause and the
    box-build examples are task 4.)

    Validates: Requirements 1.2, 1.7
    """
    outline = extract_outline(world.ter, world.safe_point)
    region = _region(world)
    pts = _segment_samples(outline)
    ok = on_floor_boundary(world.ter, region, pts, tol=0.05)
    assert ok.all(), f"outline points off the Floor_Boundary: {pts[~ok][:5].tolist()}"


# ---------------------------------------------------------------------------
# Property 3: completeness
# ---------------------------------------------------------------------------

@_synthetic_settings()
@given(world=slab_worlds())
def test_outline_completeness(world):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 3: Outline
    completeness (M2-P1).

    Synthetic part: at least 99 % of the Floor_Boundary length, sampled every
    0.5 u along every Floor_Region edge, lies within 0.05 u of an emitted
    segment.

    Validates: Requirements 1.4, 1.7
    """
    outline = extract_outline(world.ter, world.safe_point)
    frac = _covered_fraction(world, _region(world), outline)
    assert frac >= 0.99, f"only {frac:.4f} of the Floor_Boundary is drawn"


# ---------------------------------------------------------------------------
# Property 4: wall / ledge classification
# ---------------------------------------------------------------------------

def _on_wall_base(world, p, q, x) -> bool:
    """Does a wall base run along segment ``p-q`` (collinear) through ``x``?
    A base that only touches the segment at a point does not count."""
    d = (q - p) / np.linalg.norm(q - p)
    for a, b in world.wall_bases:
        a, b = np.array(a, float), np.array(b, float)
        off = lambda v: np.linalg.norm((v - p) - ((v - p) @ d) * d)  # noqa: E731
        if off(a) > 1e-6 or off(b) > 1e-6:
            continue
        ab = b - a
        t = float(np.clip((x - a) @ ab / (ab @ ab), 0.0, 1.0))
        if np.linalg.norm(a + t * ab - x) <= 1e-6:
            return True
    return False


@_synthetic_settings()
@given(world=slab_worlds())
def test_wall_ledge_classification(world):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 4: Wall and
    ledge classification (M2-P2).

    Every emitted polyline on a slab side is ``wall`` exactly where that side
    carries a rising wall quad over its span, and ``ledge`` otherwise. Checked
    at the quarter points of every segment against the recorded wall bases.

    Validates: Requirements 1.5
    """
    outline = extract_outline(world.ter, world.safe_point)
    for pl in outline.polylines:
        for p, q in zip(pl.points, pl.points[1:]):
            p, q = np.array(p), np.array(q)
            for f in (0.25, 0.5, 0.75):
                x = p + f * (q - p)
                expected = "wall" if _on_wall_base(world, p, q, x) else "ledge"
                assert pl.kind == expected, (
                    f"{pl.kind} polyline at {x.tolist()} should be {expected}")


# ---------------------------------------------------------------------------
# Property 5: reachable-only
# ---------------------------------------------------------------------------

@_synthetic_settings()
@given(world=slab_worlds(island=True))
def test_reachable_only(world):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 5:
    Reachable-only selects the walked floor (M2-P3).

    The default outline has no point within 0.05 u of the island's edges; the
    ``reachable_only=False`` outline covers the island's Floor_Boundary by the
    completeness rule; both agree exactly on the reachable part.

    Validates: Requirements 1.6
    """
    reach = extract_outline(world.ter, world.safe_point)
    full = extract_outline(world.ter, world.safe_point, reachable_only=False)

    x0, y0, x1, y1, z = world.slabs[world.island]
    island_edges = np.array([[(x0, y0, z), (x1, y0, z)], [(x1, y0, z), (x1, y1, z)],
                             [(x1, y1, z), (x0, y1, z)], [(x0, y1, z), (x0, y0, z)]], float)
    pts = _segment_samples(reach, spacing=0.25)
    assert (_dist_to_segments(pts, island_edges) > 0.05).all(), "default outline draws the island"

    # The island's own boundary is drawn in the all-floor outline.
    floor = floor_faces(world.ter)
    ipts, w, boundary = floor_boundary_samples(world.ter, floor, 0.5)
    on_island = _dist_to_segments(ipts, island_edges) <= 1e-6
    sel = boundary & on_island
    assert sel.any()
    near = _dist_to_segments(ipts[sel], _segments(full)) <= 0.05
    assert w[sel][near].sum() >= 0.99 * w[sel].sum()

    # Exact agreement on the reachable part: every default polyline appears
    # unchanged in the all-floor outline, and every extra one lies on floor the
    # walk does not reach.
    full_set = set(full.polylines)
    assert all(p in full_set for p in reach.polylines)
    region = _region(world)
    unreached = floor & ~region
    extra = [p for p in full.polylines if p not in set(reach.polylines)]
    if extra:
        tris = np.array([[(v.x, v.y, v.z) for v in (world.ter.vertices[f.v1],
                                                   world.ter.vertices[f.v2],
                                                   world.ter.vertices[f.v3])]
                         for f in world.ter.polygons])[unreached]
        edges = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
        for pl in extra:
            d = _dist_to_segments(np.array(pl.points), edges)
            assert (d <= 0.05).all(), f"extra polyline {pl.points[:3]} is not on unreached floor"


# ---------------------------------------------------------------------------
# Property 6: canonical outline
# ---------------------------------------------------------------------------

def _scramble(ter: TerFile, rnd: random.Random) -> TerFile:
    """Shuffle face order, rotate each face's vertices, renumber vertices."""
    perm = list(range(len(ter.vertices)))
    rnd.shuffle(perm)                       # new index of old vertex i = perm[i]
    verts = [None] * len(perm)
    for old, new in enumerate(perm):
        v = ter.vertices[old]
        verts[new] = Vertex(x=v.x, y=v.y, z=v.z)
    polys = []
    for p in ter.polygons:
        ids = [perm[p.v1], perm[p.v2], perm[p.v3]]
        r = rnd.randrange(3)
        ids = ids[r:] + ids[:r]
        polys.append(Polygon(v1=ids[0], v2=ids[1], v3=ids[2], material=p.material, flags=p.flags))
    rnd.shuffle(polys)
    return TerFile(name=ter.name, vertices=verts, polygons=polys)


@_synthetic_settings()
@given(world=slab_worlds(), salt=st.integers(0, 2**32 - 1))
def test_canonical_outline(world, salt):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 6: Canonical
    outline (M2-P4).

    Shuffling faces, rotating each face's vertex order and renumbering vertices
    leaves the outline unchanged (the seed face is compared by its corners, the
    one field that is an index into the TER), and every polyline has at least 2
    points with consecutive points at least 0.01 u apart.

    Validates: Requirements 1.8
    """
    a = extract_outline(world.ter, world.safe_point)
    scrambled = _scramble(world.ter, random.Random(salt))
    b = extract_outline(scrambled, world.safe_point)
    assert a.polylines == b.polylines
    assert a.bands == b.bands
    assert a.bounds == b.bounds
    assert a.reachable_only == b.reachable_only

    def corners(ter, f):
        p = ter.polygons[f]
        return sorted((v.x, v.y, v.z) for v in (ter.vertices[p.v1], ter.vertices[p.v2],
                                                 ter.vertices[p.v3]))
    seed_z = lambda ter, f: corners(ter, f)[0][2]  # noqa: E731
    # Ties between the two triangles of slab 0 under the safe point may pick
    # either; both are the same floor.
    assert seed_z(world.ter, a.seed_face) == seed_z(scrambled, b.seed_face)

    for pl in a.polylines:
        assert len(pl.points) >= 2
        for p, q in zip(pl.points, pl.points[1:]):
            assert math.dist(p, q) >= 0.01


# ---------------------------------------------------------------------------
# Property 7: depth bands
# ---------------------------------------------------------------------------

def _level_polylines(world, outline, k):
    h = world.levels[k]
    x0, y0, x1, y1 = world.column
    return [pl for pl in outline.polylines
            if all(abs(p[2] - h) <= 1e-6 and x0 <= p[0] <= x1 and y0 <= p[1] <= y1
                   for p in pl.points)]


@_synthetic_settings()
@given(world=stacked_worlds())
def test_depth_bands(world):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 7: Depth bands
    separate stacked floors (M2-P5).

    For 1-7 stacked levels (optionally a ramp, plus non-overlapping slabs): the
    outline has ``min(levels', 4)`` bands; every polyline's points lie inside
    its band's height range; the polylines of two levels share a band exactly
    when the reference model's smallest-gap merge joined them; the safe point's
    level is in the band marked ``main`` (index 0).

    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
    """
    outline = extract_outline(world.ter, world.safe_point, reachable_only=False)
    groups = reference_bands(world.levels, world.others)
    assert len(outline.bands) == len(groups) == min(len(world.levels), MAX_BANDS)
    by_index = {b.index: b for b in outline.bands}
    assert sorted(by_index) == list(range(len(outline.bands)))
    assert by_index[0].role == "main"
    assert sum(b.role == "main" for b in outline.bands) == 1

    for pl in outline.polylines:
        b = by_index[pl.band]
        for p in pl.points:
            assert b.z_lo <= p[2] <= b.z_hi, f"{p} outside band {b}"

    level_band = {}
    for k in range(len(world.levels)):
        bands = {pl.band for pl in _level_polylines(world, outline, k)}
        assert len(bands) == 1, f"level {k} drawn in bands {bands}"
        level_band[k] = bands.pop()
    group_of = {k: g for g, members in enumerate(groups) for k in members}
    for i in level_band:
        for j in level_band:
            same = group_of[i] == group_of[j]
            assert (level_band[i] == level_band[j]) == same, (i, j, groups)
    assert level_band[world.main_level] == 0


def test_depth_bands_single_level_is_main():
    """No stacked floors: one band, the Main_Band, unbounded (Req 2.2)."""
    tris = np.array([[(0, 0, 0), (10, 0, 0), (10, 10, 5)],
                     [(20, 0, 30), (30, 0, 30), (30, 10, 30)]], float)
    bands = depth_bands(FloorSet(tris), 0.0)
    assert len(bands) == 1
    b = bands[0]
    assert (b.index, b.role, b.offset) == (0, "main", 0)
    assert b.z_lo == -math.inf and b.z_hi == math.inf


def test_empty_floor_region_raises():
    """A safe point whose walk reaches no Floor_Face raises EmptyFloorRegion:
    a lone ceiling (down-facing) is standable to the validator's |n_z| rule but
    is not floor under the signed rule (Decision 1)."""
    ter = TerFile(name="ceiling")
    ter.vertices = [Vertex(0, 0, 10), Vertex(0, 10, 10), Vertex(10, 0, 10)]
    ter.polygons = [Polygon(v1=0, v2=1, v3=2)]
    with pytest.raises(EmptyFloorRegion):
        extract_outline(ter, (2.0, 2.0, 9.0))


def test_outline_summary_shape():
    ter = TerFile(name="slab")
    ter.vertices = [Vertex(0, 0, 0), Vertex(4, 0, 0), Vertex(4, 4, 0), Vertex(0, 4, 0),
                    Vertex(0, 0, 8), Vertex(4, 0, 8)]
    ter.polygons = [Polygon(v1=0, v2=1, v3=2), Polygon(v1=0, v2=2, v3=3),
                    Polygon(v1=0, v2=4, v3=5), Polygon(v1=0, v2=5, v3=1)]
    summary = outline_summary(extract_outline(ter, (2.0, 2.0, 0.25)))
    assert summary["reachable_only"] is True
    assert summary["bounds"] == [0.0, 0.0, 0.0, 4.0, 4.0, 0.0]
    (band,) = summary["bands"]
    assert band == {"index": 0, "role": "main", "z_lo": None, "z_hi": None,
                    "median_z": 0.0, "walls": 1, "ledges": 1}
