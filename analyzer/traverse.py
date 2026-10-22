"""
analyzer/traverse.py
--------------------
Mesh-based traversability validator.

Answers the question the acceptance checklist's section B (Navigability) asks a
human to walk every zone for: *can a player actually walk to every room from
the entrance?* — automatically, on the **real generated mesh** (the TER that
ships in the .eqg), not on the room graph. The room graph is used only as the
oracle for what SHOULD be reachable (every room's floor footprint); the proof
of reachability is a walk across the actual triangles.

Why the mesh and not the graph: the standing lesson in this repo is that the
graph/analysis can report "connected" while the render is broken (misaligned
stairs, cliff ramps, oversized steps all passed the structural tests and were
only caught by eye). EQ collision is per-triangle — the mesh *is* the collision
model — so a mesh walk is faithful to how the client actually moves.

The agent model
---------------
EQ scale: 1 unit ~= 1 foot, a player is ~6 units tall, Z is up. A triangle is
"standable" when its face normal points up steeply enough (slope <= the walkable
cap). Two standable triangles connect if an agent can step between them: they
are horizontally adjacent (share mesh geometry, or their footprints touch) and
the vertical gap between them at the shared boundary is within the max step-up.
This is what catches cliff ramps (slope too steep) and oversized stairs (step
gap too tall) — the exact failures per-triangle/component-count checks miss.

Usage::

    python -m analyzer.traverse output/badseed.eqg
    python -m analyzer.traverse output/badseed.eqg --spec output/badseed.json
    python -m analyzer.traverse badseed              # resolves output/badseed.*
    python -m analyzer.traverse output/badseed.eqg --slope-cap 40 --step-up 3
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.pfs import PfsArchive
from core.ter import TerFile
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec


# ---------------------------------------------------------------------------
# Agent model
# ---------------------------------------------------------------------------

@dataclass
class AgentModel:
    """
    The walking agent, in EQ world units (1u ~= 1 foot; player ~6u tall; Z up).

    walkable_slope_deg
        Maximum surface slope the agent can stand on / climb. 40 deg matches the
        dungeon/cave terrain backend's ``max_walkable_grad = 0.85`` (tan 40 deg
        ~= 0.84). Faces steeper than this are "unwalkable" (cliff ramps).
    max_step_up
        Maximum vertical gap between two otherwise-adjacent walkable surfaces the
        agent can step up/over. EQ's client step tolerance is small relative to
        the ~6u player height; a 15u stair step is plainly impassable, a ~7u step
        is borderline-too-tall. 3.0u is a generous-but-honest climbable gap.
    adjacency_eps
        Horizontal tolerance (world units) for treating two triangle footprints
        as touching when they don't share a mesh edge. Covers T-junctions and the
        seams where a corridor mesh meets a room floor mesh.
    """
    walkable_slope_deg: float = 40.0
    max_step_up: float = 3.0
    adjacency_eps: float = 2.0
    player_height: float = 6.0

    @property
    def min_up_normal(self) -> float:
        """normal.z threshold: cos(slope) for a standable face."""
        return math.cos(math.radians(self.walkable_slope_deg))


# ---------------------------------------------------------------------------
# Report structures
# ---------------------------------------------------------------------------

@dataclass
class RoomResult:
    room_id: str
    role: str
    reachable: bool
    floor_faces: int             # standable faces inside the room footprint
    reached_faces: int           # of those, how many are in the reachable set
    reason: str = ""             # why unreachable (empty if reachable)


@dataclass
class TraversalReport:
    zone_name: str
    agent: AgentModel
    total_rooms: int
    reachable_rooms: int
    rooms: List[RoomResult] = field(default_factory=list)
    # Diagnostics about the mesh as a whole
    total_faces: int = 0
    standable_faces: int = 0
    reachable_faces: int = 0
    seed_face: Optional[int] = None
    notes: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.total_rooms > 0 and self.reachable_rooms == self.total_rooms

    def summary(self) -> str:
        lines: List[str] = []
        status = "PASS" if self.passed else "FAIL"
        lines.append(f"[{status}] traversability: {self.zone_name}")
        lines.append(
            f"  agent: slope<={self.agent.walkable_slope_deg:.0f}deg  "
            f"step-up<={self.agent.max_step_up:.1f}u  "
            f"player~{self.agent.player_height:.0f}u"
        )
        lines.append(
            f"  mesh:  {self.total_faces} faces  "
            f"{self.standable_faces} standable  "
            f"{self.reachable_faces} reachable from safe point"
        )
        lines.append(
            f"  rooms: {self.reachable_rooms}/{self.total_rooms} reachable"
        )
        for r in self.rooms:
            mark = "OK " if r.reachable else "XX "
            detail = f"floor_faces={r.floor_faces} reached={r.reached_faces}"
            if r.reachable:
                lines.append(f"    {mark}{r.room_id:<10} [{r.role}] {detail}")
            else:
                lines.append(
                    f"    {mark}{r.room_id:<10} [{r.role}] {detail}  -> {r.reason}"
                )
        for n in self.notes:
            lines.append(f"  note: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mesh loading
# ---------------------------------------------------------------------------

def load_ter_from_eqg(eqg_path: str | Path) -> Tuple[TerFile, str]:
    """
    Load the zone's terrain TER out of its .eqg. Returns (ter, zone_name).

    The builder packs the ground mesh as ``ter_<zone>.ter`` (RoF2 convention),
    so try that first, then any .ter in the archive.
    """
    path = Path(eqg_path)
    zone_name = path.stem.lower()
    arc = PfsArchive.from_file(path)

    ter_data = arc.get(f"ter_{zone_name}.ter")
    if ter_data is None:
        ter_data = arc.get(f"{zone_name}.ter")
    if ter_data is None:
        ter_files = arc.get_by_extension("ter")
        if not ter_files:
            raise ValueError(f"No .ter mesh found in {path}")
        ter_data = ter_files[0].data

    ter = TerFile.from_bytes(ter_data, name=zone_name)
    return ter, zone_name


# ---------------------------------------------------------------------------
# Surface extraction + walkable adjacency
# ---------------------------------------------------------------------------

@dataclass
class WalkSurface:
    """Per-triangle walkable-surface model derived from the TER mesh."""
    verts: np.ndarray             # (V, 3) float
    faces: np.ndarray             # (F, 3) int
    normals: np.ndarray           # (F, 3) geometric face normals (unit)
    centroids: np.ndarray         # (F, 3)
    standable: np.ndarray         # (F,) bool
    adjacency: Dict[int, List[int]]   # standable face -> neighbouring standable faces


# ---------------------------------------------------------------------------
# XY contact geometry (footprint-proximity adjacency)
# ---------------------------------------------------------------------------
#
# Two standable triangles are walkably adjacent across a mesh seam only when
# their floors ACTUALLY MEET: their XY footprints touch (overlap, or abut within
# adjacency_eps) AND the two floor heights agree where they touch (within
# max_step_up). The old test asked only whether the two XY BOUNDING BOXES came
# within eps on each axis independently, which "touches" triangles that are
# tens of units apart (offset on the other axis) or stacked at different heights
# -- that is the source of the false PASSes. These helpers do the honest test:
# the true minimum XY distance between the two triangles, and each triangle's
# interpolated floor height at the point where they come closest.

def _point_in_tri_xy(px: float, py: float, tri: np.ndarray) -> bool:
    """Is (px, py) inside triangle ``tri`` (XY projection, inclusive edges)?"""
    ax, ay = tri[0, 0], tri[0, 1]
    bx, by = tri[1, 0], tri[1, 1]
    cx, cy = tri[2, 0], tri[2, 1]
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(det) < 1e-12:
        return False
    l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
    l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
    l3 = 1.0 - l1 - l2
    tol = 1e-9
    return l1 >= -tol and l2 >= -tol and l3 >= -tol


def _seg_seg_closest_xy(p1, p2, p3, p4):
    """
    Closest pair of points between 2D segments p1p2 and p3p4. Returns
    (distance, mid_xy) where mid_xy is the midpoint of the closest pair.
    """
    p1 = np.asarray(p1, float); p2 = np.asarray(p2, float)
    p3 = np.asarray(p3, float); p4 = np.asarray(p4, float)

    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])

    # Proper intersection -> distance 0 at the crossing point.
    d1, d2 = ccw(p3, p4, p1), ccw(p3, p4, p2)
    d3, d4 = ccw(p1, p2, p3), ccw(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        den = (p1[0] - p2[0]) * (p3[1] - p4[1]) - (p1[1] - p2[1]) * (p3[0] - p4[0])
        if abs(den) > 1e-12:
            t = ((p1[0] - p3[0]) * (p3[1] - p4[1]) -
                 (p1[1] - p3[1]) * (p3[0] - p4[0])) / den
            ip = p1 + t * (p2 - p1)
            return 0.0, ip
        return 0.0, (p1 + p3) * 0.5

    def pt_seg(p, a, b):
        ab = b - a
        denom = ab.dot(ab)
        t = 0.0 if denom <= 1e-12 else float(np.clip((p - a).dot(ab) / denom, 0.0, 1.0))
        proj = a + t * ab
        return float(np.linalg.norm(p - proj)), proj

    best_d = float("inf")
    best_mid = None
    for p, a, b in ((p1, p3, p4), (p2, p3, p4), (p3, p1, p2), (p4, p1, p2)):
        d, proj = pt_seg(p, a, b)
        if d < best_d:
            best_d = d
            best_mid = (p + proj) * 0.5
    return best_d, best_mid


def _tri_tri_xy_contact(ti: np.ndarray, tj: np.ndarray):
    """
    Minimum XY distance between triangles ``ti`` and ``tj`` and a representative
    contact point. Returns (distance, point_xy). Distance is 0 when they
    genuinely overlap (a vertex of one inside the other, or edges crossing);
    otherwise it is the closest edge-to-edge gap. ``point_xy`` is where they
    come closest -- the spot to compare floor heights at.
    """
    # Containment: a vertex of one triangle inside the other => real overlap.
    for v in ti[:3, :2]:
        if _point_in_tri_xy(v[0], v[1], tj):
            return 0.0, np.asarray(v, float)
    for v in tj[:3, :2]:
        if _point_in_tri_xy(v[0], v[1], ti):
            return 0.0, np.asarray(v, float)

    ei = [(ti[k, :2], ti[(k + 1) % 3, :2]) for k in range(3)]
    ej = [(tj[k, :2], tj[(k + 1) % 3, :2]) for k in range(3)]
    best_d = float("inf")
    best_pt = None
    for a, b in ei:
        for c2, d2 in ej:
            d, mid = _seg_seg_closest_xy(a, b, c2, d2)
            if d < best_d:
                best_d = d
                best_pt = mid
                if best_d == 0.0:
                    return best_d, best_pt
    return best_d, best_pt


def _plane_z_at(tri: np.ndarray, px: float, py: float) -> float:
    """
    Height of the plane through ``tri`` at (px, py), via barycentric
    interpolation on the XY projection. Falls back to the mean vertex Z when the
    triangle is XY-degenerate.
    """
    ax, ay = tri[0, 0], tri[0, 1]
    bx, by = tri[1, 0], tri[1, 1]
    cx, cy = tri[2, 0], tri[2, 1]
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(det) < 1e-12:
        return float((tri[0, 2] + tri[1, 2] + tri[2, 2]) / 3.0)
    l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
    l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
    l3 = 1.0 - l1 - l2
    return float(l1 * tri[0, 2] + l2 * tri[1, 2] + l3 * tri[2, 2])


def build_walk_surface(ter: TerFile, agent: AgentModel) -> WalkSurface:
    """
    Classify standable triangles and build walkable adjacency between them.

    A face is standable when its geometric normal points up within the walkable
    slope cap. Two standable faces are adjacent (the agent can walk between them)
    when their floors genuinely MEET: either they share a mesh vertex (an exact
    weld -- one 3D point, zero step), or their XY footprints actually touch (true
    triangle overlap, or an edge-to-edge gap within ``adjacency_eps`` by the real
    minimum XY distance) AND their interpolated floor heights AT THAT CONTACT
    POINT are within the step-up height. Comparing Z at the contact -- not at the
    two centroids -- and requiring true contact rather than a per-axis
    bounding-box clip is what keeps the gate sound: faces that merely overlap in
    XY while offset on the other axis, or stacked at different heights, do not
    connect.
    """
    verts = np.array([[v.x, v.y, v.z] for v in ter.vertices], dtype=np.float64)
    faces = np.array([[p.v1, p.v2, p.v3] for p in ter.polygons], dtype=np.int64)

    if len(faces) == 0:
        return WalkSurface(verts, faces, np.zeros((0, 3)), np.zeros((0, 3)),
                           np.zeros(0, bool), {})

    a = verts[faces[:, 0]]
    b = verts[faces[:, 1]]
    c = verts[faces[:, 2]]
    raw_n = np.cross(b - a, c - a)
    lens = np.linalg.norm(raw_n, axis=1)
    safe = lens > 1e-9
    normals = np.zeros_like(raw_n)
    normals[safe] = raw_n[safe] / lens[safe, None]
    centroids = (a + b + c) / 3.0

    # Standable: normal points up (either winding) steeply enough. We use |nz|
    # so winding direction doesn't matter — what matters is the face is near
    # horizontal and faces the sky.
    nz = np.abs(normals[:, 2])
    standable = safe & (nz >= agent.min_up_normal)

    std_idx = np.nonzero(standable)[0]

    # ---- Adjacency ----------------------------------------------------------
    # 1) Shared-vertex adjacency (cheap, exact mesh connectivity).
    vert_to_faces: Dict[int, List[int]] = {}
    for fi in std_idx:
        for vi in faces[fi]:
            vert_to_faces.setdefault(int(vi), []).append(int(fi))

    adjacency: Dict[int, List[int]] = {int(fi): set() for fi in std_idx}

    # Two faces that share a mesh vertex (same index) meet EXACTLY at that
    # vertex in 3D -- they already agree in Z there (it is one point), so the
    # step across that seam is zero and they are walkably connected. This is the
    # vertex-based form of the step check: a welded seam has no step to clear,
    # so the old centroid-Z gate here was a spurious proxy that could wrongly
    # cut a legitimately-welded pair of standable faces. We keep this pass as the
    # exact mesh-connectivity backbone and drop the centroid test.
    for vi, flist in vert_to_faces.items():
        for i in range(len(flist)):
            for j in range(i + 1, len(flist)):
                fi, fj = flist[i], flist[j]
                adjacency[fi].add(fj)
                adjacency[fj].add(fi)

    # 2) Footprint-contact adjacency across mesh seams (corridor->room joins
    #    where vertices don't coincide). Spatial hash on XY to keep it O(F).
    #    Two faces connect ONLY when their XY footprints genuinely touch (true
    #    triangle overlap, or an edge-to-edge gap within adjacency_eps) AND their
    #    interpolated floor heights AT THAT CONTACT POINT are within max_step_up.
    #    Comparing Z at the contact -- not the two centroids -- is the fix: a room
    #    floor and a ramp/jog passing over the same XY at a different height no
    #    longer wire together, and two slabs whose bounding boxes merely clip by a
    #    couple of units on each axis while sitting tens of units apart in the
    #    other no longer "touch".
    eps = agent.adjacency_eps
    tris = np.stack([a, b, c], axis=1)  # (F, 3, 3): per-face vertex positions
    fxy_min = np.minimum(np.minimum(a, b), c)[:, :2]
    fxy_max = np.maximum(np.maximum(a, b), c)[:, :2]

    cell = max(eps * 4.0, 16.0)
    grid: Dict[Tuple[int, int], List[int]] = {}

    def _cells_for(fi: int):
        lo = fxy_min[fi] - eps
        hi = fxy_max[fi] + eps
        cx0, cy0 = int(math.floor(lo[0] / cell)), int(math.floor(lo[1] / cell))
        cx1, cy1 = int(math.floor(hi[0] / cell)), int(math.floor(hi[1] / cell))
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                yield (cx, cy)

    for fi in std_idx:
        for key in _cells_for(int(fi)):
            grid.setdefault(key, []).append(int(fi))

    def _bbox_near(fi: int, fj: int) -> bool:
        # Cheap reject before the exact test: XY bounding boxes within eps.
        return (fxy_min[fi, 0] - eps <= fxy_max[fj, 0] and
                fxy_max[fi, 0] + eps >= fxy_min[fj, 0] and
                fxy_min[fi, 1] - eps <= fxy_max[fj, 1] and
                fxy_max[fi, 1] + eps >= fxy_min[fj, 1])

    seen_pairs: set = set()
    for key, flist in grid.items():
        for i in range(len(flist)):
            for j in range(i + 1, len(flist)):
                fi, fj = flist[i], flist[j]
                if fj in adjacency[fi]:
                    continue
                pk = (fi, fj) if fi < fj else (fj, fi)
                if pk in seen_pairs:
                    continue
                seen_pairs.add(pk)
                if not _bbox_near(fi, fj):
                    continue
                # True XY contact test: do the triangles actually touch?
                dist, pt = _tri_tri_xy_contact(tris[fi], tris[fj])
                if pt is None or dist > eps:
                    continue
                # Floors must agree in height WHERE they touch, not at centroids.
                zi = _plane_z_at(tris[fi], pt[0], pt[1])
                zj = _plane_z_at(tris[fj], pt[0], pt[1])
                if abs(zi - zj) <= agent.max_step_up:
                    adjacency[fi].add(fj)
                    adjacency[fj].add(fi)

    adjacency_lists = {k: sorted(v) for k, v in adjacency.items()}
    return WalkSurface(verts, faces, normals, centroids, standable, adjacency_lists)


# ---------------------------------------------------------------------------
# Flood fill + room mapping
# ---------------------------------------------------------------------------

def _nearest_standable_face(surf: WalkSurface, point: np.ndarray,
                            xy_radius: float) -> Optional[int]:
    """
    Pick the standable face to start the walk from: the one whose footprint
    contains (or is nearest, within xy_radius) the safe point in XY, preferring
    the face whose centroid Z is closest to the safe point's Z (stand on the
    floor at that spot, not a surface far above/below it).
    """
    std_idx = np.nonzero(surf.standable)[0]
    if len(std_idx) == 0:
        return None
    cen = surf.centroids[std_idx]
    dxy = np.linalg.norm(cen[:, :2] - point[:2], axis=1)
    within = dxy <= xy_radius
    cand = std_idx[within]
    if len(cand) == 0:
        # fall back to globally nearest in XY
        return int(std_idx[int(np.argmin(dxy))])
    cz = surf.centroids[cand]
    dz = np.abs(cz[:, 2] - point[2])
    return int(cand[int(np.argmin(dz))])


def flood_reachable(surf: WalkSurface, seed_face: int) -> set:
    """BFS across the walkable adjacency graph from the seed face."""
    reached: set = set()
    if seed_face is None or seed_face not in surf.adjacency:
        return reached
    stack = [seed_face]
    reached.add(seed_face)
    while stack:
        f = stack.pop()
        for nb in surf.adjacency.get(f, ()):  # type: ignore[arg-type]
            if nb not in reached:
                reached.add(nb)
                stack.append(nb)
    return reached


def _faces_in_room(surf: WalkSurface, room: RoomSpec) -> np.ndarray:
    """
    Indices of standable faces whose floor lies within the room footprint.

    The footprint test is primarily an XY question — "is there walkable floor
    under this room's area?". Z is used only to disambiguate when multiple
    walkable surfaces stack at the same XY (e.g. a box dungeon where a room's
    floor sits directly above/below another room's): we prefer the faces nearest
    the room's own floor height. For open terrain (outdoor/cave), the nominal
    ``floor_z`` won't match the undulating heightfield, so if the Z band selects
    nothing we fall back to all XY-matching faces — the terrain IS the floor.
    """
    (xmin, ymin, zmin), (xmax, ymax, zmax) = room.bounds
    std_idx = np.nonzero(surf.standable)[0]
    cen = surf.centroids[std_idx]

    in_xy = (
        (cen[:, 0] >= xmin) & (cen[:, 0] <= xmax) &
        (cen[:, 1] >= ymin) & (cen[:, 1] <= ymax)
    )
    xy_idx = std_idx[in_xy]
    if len(xy_idx) == 0:
        return xy_idx

    xy_cen = cen[in_xy]
    # Prefer faces near this room's floor (box dungeon: a room is a slab of
    # floor at floor_z; a surface up near the ceiling or in a stacked neighbour
    # shouldn't count). Band: from a step below the floor up through the room.
    zlo = zmin - FLOOR_Z_TOL
    zhi = zmax + 4.0
    in_z = (xy_cen[:, 2] >= zlo) & (xy_cen[:, 2] <= zhi)
    if in_z.any():
        return xy_idx[in_z]
    # Terrain case: no face in the nominal floor band — the open ground under
    # this footprint IS the room floor. Return the XY matches (the flood fill
    # decides reachability).
    return xy_idx


FLOOR_Z_TOL = 8.0


def classify_corridor(corr: CorridorSpec, agent: AgentModel) -> Tuple[bool, str]:
    """
    Judge a corridor's intended geometry against the agent, from the spec alone.

    Returns (walkable, reason). This is the "why" oracle: when a room is
    unreachable and the corridor that should serve it is itself a cliff ramp or
    an oversized staircase, we can name that precisely instead of a generic gap.
    A flat/shallow corridor returns walkable=True (so the break is elsewhere —
    a true mesh disconnect).
    """
    dz = abs(corr.to_z - corr.from_z)
    run = math.hypot(corr.to_x - corr.from_x, corr.to_y - corr.from_y)
    if dz < 1e-3:
        return True, "flat"
    if corr.steps and corr.steps > 0:
        step = dz / corr.steps
        if step > agent.max_step_up:
            return False, (f"stair step ~{step:.1f}u exceeds step-up "
                           f"{agent.max_step_up:.1f}u (too tall to climb)")
        return True, f"stairs ~{step:.1f}u/step"
    # Ramp: slope angle vs the walkable cap.
    slope = math.degrees(math.atan2(dz, max(run, 1e-6)))
    if slope > agent.walkable_slope_deg:
        return False, (f"ramp {slope:.0f}deg exceeds walkable cap "
                       f"{agent.walkable_slope_deg:.0f}deg (cliff ramp)")
    return True, f"ramp {slope:.0f}deg"


def _diagnose_via_graph(room_id: str, spec: ZoneSpec, agent: AgentModel,
                        reachable_room_ids: set) -> Optional[str]:
    """
    Use the corridor graph to name the offending corridor for an unreachable
    room: find a corridor joining this room to an already-reachable room and, if
    that corridor's own geometry is unwalkable, report it (cliff ramp / oversized
    step). Returns None if the graph doesn't explain it (then fall back to the
    mesh-geometry guess).
    """
    best: Optional[str] = None
    for c in spec.corridors:
        ends = {c.from_room, c.to_room}
        if room_id not in ends:
            continue
        other = (ends - {room_id}).pop() if len(ends) == 2 else ""
        walkable, why = classify_corridor(c, agent)
        if not walkable:
            via = f" (reachable from {other})" if other in reachable_room_ids else ""
            return f"{c.id} {c.from_room}->{c.to_room}: {why}{via}"
        if other in reachable_room_ids and best is None:
            # A walkable corridor from a reachable room that still didn't connect
            # on the mesh: the mesh join is broken (misaligned opening / gap).
            best = (f"{c.id} from reachable {other} is nominally walkable ({why}) "
                    f"but its mesh opening doesn't meet {room_id} "
                    f"(misaligned/detached corridor)")
    return best


def _diagnose_unreachable(surf: WalkSurface, agent: AgentModel,
                          room_faces: np.ndarray, reachable: set) -> str:
    """
    Best-effort reason why a room's floor couldn't be reached.

    Looks at the room's floor faces and the nearest reachable face to guess the
    failure class: a too-steep ramp between them (cliff), a vertical gap beyond
    step-up (oversized stair / drop), or no nearby walkable surface at all
    (sealed room / disconnected corridor / floating geometry).
    """
    if len(room_faces) == 0:
        return "no standable floor in room footprint (sealed, floating, or steep floor)"

    reachable_idx = np.array(sorted(reachable), dtype=np.int64)
    if len(reachable_idx) == 0:
        return "nothing reachable from safe point (entrance not on walkable floor?)"

    room_cen = surf.centroids[room_faces]
    reach_cen = surf.centroids[reachable_idx]

    # Nearest reachable face to any room floor face (XY distance).
    best_xy = float("inf")
    best_dz = 0.0
    for rc in room_cen:
        dxy = np.linalg.norm(reach_cen[:, :2] - rc[:2], axis=1)
        k = int(np.argmin(dxy))
        if dxy[k] < best_xy:
            best_xy = float(dxy[k])
            best_dz = float(abs(reach_cen[k, 2] - rc[2]))

    if best_xy <= agent.adjacency_eps + 4.0 and best_dz > agent.max_step_up:
        return (f"vertical gap ~{best_dz:.1f}u to nearest walkable surface "
                f"exceeds step-up {agent.max_step_up:.1f}u "
                f"(oversized stair step or drop)")
    if best_xy <= 40.0 and best_dz > agent.max_step_up:
        return (f"nearest walkable surface is {best_xy:.0f}u away and "
                f"{best_dz:.1f}u higher/lower (unwalkable ramp/cliff or step gap)")
    return (f"nearest walkable surface is {best_xy:.0f}u away in XY "
            f"(disconnected corridor or gap in the mesh)")


# ---------------------------------------------------------------------------
# Top-level validation
# ---------------------------------------------------------------------------

def validate(eqg_path: str | Path,
             spec: Optional[ZoneSpec] = None,
             spec_path: Optional[str | Path] = None,
             agent: Optional[AgentModel] = None) -> TraversalReport:
    """
    Load the mesh and room graph, walk the mesh from the safe point, and report
    per-room reachability.
    """
    agent = agent or AgentModel()
    ter, zone_name = load_ter_from_eqg(eqg_path)

    if spec is None:
        if spec_path is None:
            # Default: sibling <zone>.json next to the .eqg
            spec_path = Path(eqg_path).with_suffix(".json")
        spec_path = Path(spec_path)
        if not spec_path.exists():
            raise ValueError(
                f"Room-graph spec not found: {spec_path}. Pass --spec explicitly."
            )
        spec = ZoneSpec.load(spec_path)

    surf = build_walk_surface(ter, agent)
    report = TraversalReport(
        zone_name=zone_name,
        agent=agent,
        total_rooms=len(spec.rooms),
        reachable_rooms=0,
        total_faces=len(surf.faces),
        standable_faces=int(surf.standable.sum()),
    )

    safe = np.array(spec.safe_point, dtype=np.float64)
    # XY search radius for the start face: generous so a safe point placed at the
    # entrance room centre still lands on its floor.
    seed_face = _nearest_standable_face(surf, safe, xy_radius=400.0)
    report.seed_face = seed_face
    if seed_face is None:
        report.notes.append("no standable face anywhere in the mesh")
        for room in spec.rooms:
            report.rooms.append(RoomResult(room.id, room.role, False, 0, 0,
                                           "mesh has no walkable surface"))
        return report

    reachable = flood_reachable(surf, seed_face)
    report.reachable_faces = len(reachable)

    # First pass: determine reachability per room (needed before graph diagnosis,
    # which asks "is this unreachable room adjacent to a reachable one?").
    room_faces_by_id: Dict[str, np.ndarray] = {}
    reached_by_id: Dict[str, List[int]] = {}
    for room in spec.rooms:
        rf = _faces_in_room(surf, room)
        room_faces_by_id[room.id] = rf
        reached_by_id[room.id] = [int(f) for f in rf if int(f) in reachable]
    reachable_room_ids = {rid for rid, rl in reached_by_id.items() if rl}

    for room in spec.rooms:
        room_faces = room_faces_by_id[room.id]
        reached_here = reached_by_id[room.id]
        is_reachable = len(reached_here) > 0
        reason = ""
        if not is_reachable:
            # Prefer the corridor-graph explanation (names the offending
            # corridor + the exact failure: cliff ramp / oversized step);
            # fall back to the mesh-geometry guess.
            reason = _diagnose_via_graph(room.id, spec, agent, reachable_room_ids)
            if not reason:
                reason = _diagnose_unreachable(surf, agent, room_faces, reachable)
        report.rooms.append(RoomResult(
            room_id=room.id,
            role=room.role,
            reachable=is_reachable,
            floor_faces=int(len(room_faces)),
            reached_faces=len(reached_here),
            reason=reason,
        ))
        if is_reachable:
            report.reachable_rooms += 1

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_eqg(arg: str, output_dir: str) -> Path:
    """Accept either a path to an .eqg or a bare zone name under the output dir."""
    p = Path(arg)
    if p.suffix.lower() == ".eqg" and p.exists():
        return p
    if p.exists() and p.is_file():
        return p
    cand = Path(output_dir) / f"{arg}.eqg"
    if cand.exists():
        return cand
    # last resort: return the given path so the error message is clear
    return p


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate that every room in a generated zone is reachable "
                    "on foot from the safe point, walking the real TER mesh."
    )
    parser.add_argument("zone", help="Path to .eqg, or a zone name under --output")
    parser.add_argument("--spec", help="Path to the ZoneSpec .json "
                                        "(default: <zone>.json next to the .eqg)")
    parser.add_argument("--output", default="output",
                        help="Output dir to resolve a bare zone name (default: output)")
    parser.add_argument("--slope-cap", type=float, default=40.0,
                        help="Max walkable slope in degrees (default: 40)")
    parser.add_argument("--step-up", type=float, default=3.0,
                        help="Max climbable vertical step in world units (default: 3.0)")
    args = parser.parse_args()

    eqg = _resolve_eqg(args.zone, args.output)
    agent = AgentModel(walkable_slope_deg=args.slope_cap, max_step_up=args.step_up)

    spec_path = args.spec
    if spec_path is None and eqg.suffix.lower() == ".eqg":
        spec_path = eqg.with_suffix(".json")

    try:
        rep = validate(eqg, spec_path=spec_path, agent=agent)
    except Exception as e:  # noqa: BLE001 - CLI boundary, show a clean message
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

    print(rep.summary())
    sys.exit(0 if rep.passed else 1)
