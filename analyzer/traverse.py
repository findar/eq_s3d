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
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from core.pfs import PfsArchive
from core.ter import FLAG_PASSABLE, TerFile
from scipy.ndimage import binary_dilation, binary_erosion, label

from generators.geometry import (MeshBuilder, _bridge_slots, _door_openings, bridge_layout,
                                 is_auto_stair, stair_layout)
from generators.routing import Rect, corridor_route, route_footprint
from generators.semantics import body_height
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

if TYPE_CHECKING:
    from analyzer.footprints import Placed


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

    @property
    def min_tread(self) -> float:
        """Shortest stair tread the agent can stand on: ``adjacency_eps``.

        The walk joins two floor faces whose footprints come within
        ``adjacency_eps`` of each other in XY. A tread shorter than that lets
        the tread below it and the tread above it "touch", so the agent model
        can no longer tell the tread apart from a seam: it is not a place to
        stand, only a crack between two risers. Tied to the agent so a finer
        seam tolerance allows finer treads. (Generated stairs start at a 4 u
        tread, design "Staircases".)
        """
        return self.adjacency_eps


# ---------------------------------------------------------------------------
# Bowl-gate parameters (wilderness; defaulted so the dungeon gate is unchanged)
# ---------------------------------------------------------------------------
#
# The dungeon/city gate asks one question: "is every ROOM reachable from the
# safe point?" — a full-connectivity flood over the whole walk surface. A
# wilderness zone needs two MORE guarantees proved on the same built mesh
# (Requirement 4): reachability among ONLY the playable interior (scenic rim /
# distant mountains are deliberately unreachable and must NOT be required —
# Req 4.1/12.3), and that the Spawn flood does NOT escape the bowl except
# through a declared `zoneline` gap (the Rim-seal check — Req 4.3/4.4).
#
# ``BowlGateParams`` carries exactly those extra inputs, and NOTHING about it
# touches the default path: ``validate(bowl=None)`` runs the identical flood and
# produces the identical ``TraversalReport`` the dungeon gate always has. The
# params are supplied (by wave-4 task 10.2, which implements the invariant on
# top of this plumbing) only for a wilderness build.
#
# --- Off-map / zoneline marker representation (Open Decision, RESOLVED here) ---
#
# The design left open how the "exterior / off-map" marker the Rim-seal check
# floods against is represented on the mesh. The two candidates were:
#
#   (a) SENTINEL FACES — synthesize a thin strip of fake triangles just beyond
#       each non-`zoneline` Rim segment and splice them into the walk surface so
#       the flood can "reach the exterior" as ordinary adjacency.
#   (b) EXTERIOR XY BAND — declare a 2D region (an axis-aligned XY rect per
#       non-`zoneline` segment) sitting OUTSIDE the rim ridge, and after the
#       normal Spawn flood, check whether any REACHED face's centroid XY falls
#       inside that band. No mesh mutation at all.
#
# CHOICE: **(b) exterior XY band.** Why:
#   * It reuses the existing surface and flood UNTOUCHED — ``build_walk_surface``
#     and ``flood_reachable`` run exactly as for a dungeon; the bowl check is a
#     pure post-flood test over ``surf.centroids`` of the reached set. The task's
#     hard rule is "reuse the existing agent + surface builder, do NOT invent a
#     parallel surface builder"; sentinel faces would mean synthesizing geometry
#     and wiring it into the union-find/adjacency — exactly a parallel builder.
#   * Soundness matches the sealing mechanism. A `mountain` segment seals by
#     slope (its rim faces are non-standable, so the flood never climbs the
#     ridge); a `river` segment seals via the Invisible_Wall excluding
#     beyond-edge faces from adjacency. In BOTH cases the walkable floor simply
#     stops before the exterior band — so "did a reached face land in the band?"
#     is a faithful proxy for "did the flood escape the bowl here?" A sentinel
#     face would have to be glued on with the SAME adjacency rules to be
#     faithful anyway, buying nothing over testing the band directly.
#   * It is the cleaner thing for 10.2 to consume: the band is plain data
#     (rects), trivially derived from the matrix perimeter geometry, and the
#     check is a vectorised point-in-rect over the reached centroids. A zoneline
#     gap, by contrast, is asserted reachable-and-leading-off-map by placing its
#     OWN band and requiring a reached face in it — the same primitive, inverted.
#
# So an off-map marker IS an ``OffMapBand`` (an XY rect tagged with the Rim
# segment it guards and whether it is the intended `zoneline` leak). 10.2 floods
# as today, then checks the reached centroids against these bands.


@dataclass
class OffMapBand:
    """An exterior XY region just beyond one Rim segment, for the seal check.

    The band is an axis-aligned rectangle ``(x0, y0, x1, y1)`` in world XY lying
    OUTSIDE the rim ridge of segment ``segment_id``. ``is_zoneline`` marks the
    one intended leak: for a `zoneline` segment the gate REQUIRES a reached face
    in the band (the gap leads off-map, Req 4.5); for every other (`mountain` /
    `river`) segment the gate FORBIDS any reached face in the band (reaching it
    is a bowl-leak, Req 4.4). This is the resolved representation of the off-map
    marker — an exterior band the reachable set is checked against, not a
    sentinel face spliced into the mesh (see the module note above).

    Produced from the matrix perimeter by task 10.2 / the bowl assembler; a
    verdict is computed by :func:`reached_off_map_segments`.
    """
    segment_id: str
    band: Tuple[float, float, float, float]   # (x0, y0, x1, y1) world XY
    is_zoneline: bool = False


@dataclass
class BowlGateParams:
    """The defaulted extra inputs that turn the dungeon gate into the bowl gate.

    Every field defaults to empty/None so that a ``validate`` call that does not
    pass a ``BowlGateParams`` (the dungeon/city path) is byte-for-byte the
    gate it always was — no field here is consulted on that path.

    playable_mask
        The set of standable face indices that count as *playable* interior
        (Spawn ground + playable POI anchors/ground). When supplied, the bowl
        gate (10.2) proves reachability among ONLY these faces, so scenic rim /
        distant-mountain faces are not required to be reachable (Req 4.1, 12.3).
        ``None`` means "no playable restriction" — the whole walk surface, i.e.
        today's full-connectivity semantics.
    off_map_bands
        The exterior XY bands guarding each Rim segment (one per non-`zoneline`
        segment to forbid, plus one per `zoneline` gap to require). Empty means
        the Rim-seal check is not run.
    spawn_point
        The world point the bowl flood seeds from (Spawn). ``None`` falls back to
        the spec's ``safe_point`` — the same seed the dungeon gate already uses —
        so leaving it unset changes nothing.
    """
    playable_mask: Optional[set] = None
    off_map_bands: List[OffMapBand] = field(default_factory=list)
    spawn_point: Optional[Tuple[float, float, float]] = None


def reached_off_map_segments(surf: "WalkSurface", reached: set,
                             bands: List[OffMapBand]) -> Dict[str, bool]:
    """Which off-map bands the Spawn flood landed in — the Rim-seal primitive.

    Pure helper (no verdict, no pass/fail): given a completed reachable set
    (face indices from :func:`flood_reachable`) and the exterior ``bands``,
    returns ``{segment_id: reached_into_band}`` — True iff at least one reached
    standable face has its centroid XY inside that band's rectangle. This is the
    single point-in-rect-over-reached-centroids test the resolved off-map-band
    representation needs; the ACTUAL bowl invariant (task 10.2) interprets the
    result: for a non-`zoneline` segment ``True`` is a bowl-leak naming the
    segment (Req 4.4); for a `zoneline` segment ``True`` is the required,
    intended leak (Req 4.5).

    Separated out here (rather than in 10.2) because it is the mechanical
    consequence of CHOOSING the exterior-XY-band representation, and keeping it
    beside the dataclass lets 10.2's invariant read as plain policy over this
    primitive. It never mutates the surface or the reached set.
    """
    result: Dict[str, bool] = {}
    if not bands:
        return result
    if reached:
        reached_idx = np.fromiter(reached, dtype=np.int64, count=len(reached))
        cen = surf.centroids[reached_idx]
        rx, ry = cen[:, 0], cen[:, 1]
    else:
        rx = ry = np.zeros(0, dtype=np.float64)
    for b in bands:
        x0, y0, x1, y1 = b.band
        if len(rx):
            inside = ((rx >= x0) & (rx <= x1) & (ry >= y0) & (ry <= y1))
            result[b.segment_id] = bool(inside.any())
        else:
            result[b.segment_id] = False
    return result


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
class CorridorResult:
    """One corridor's floor-continuity verdict (Requirement 5.2).

    A corridor is ``connected`` when a walkable path exists FROM its ``from_room``
    floor TO its ``to_room`` floor *within the corridor's own region* — the route
    footprint (grown by the agent's adjacency tolerance) plus the two rooms'
    footprints, MINUS every other room's footprint. Excluding third-room
    footprints (design decision: the continuity path may not enter a third
    room's footprint) is what turns a corridor that only "reaches" its far room
    by cutting through room C — through C's collidable walls, a path no player
    has — into a reported failure instead of a silent pass.

    ``reason`` is "" when connected, else one of:
      * ``"no floor in from_room"`` — no standable floor face in A's footprint
        within the region.
      * ``"no floor in to_room"``   — likewise for B.
      * ``"gap"``                   — floor at both ends but no walkable path
        between them in the region.
      * ``"crosses room <id>"``     — not connected AND a route leg penetrates a
        third room by more than ``adjacency_eps`` (the far room is only
        reachable through that room).
      * ``"conflicts with corridor <id>"`` — set by the corridor–corridor
        conflict check (design decision 16), independent of the flood above.
    """
    corridor_id: str
    from_room: str
    to_room: str
    connected: bool
    reason: str = ""


@dataclass
class OutlineResult:
    """One shaped room's verdict (step 8, Requirement 3). ``reason`` is "" when it
    passes, else one of:

      * ``"door without a throat at <side> <c0>..<c1>"``
      * ``"throat <rect> does not reach the core"``
      * ``"wall across throat <rect>"``
      * ``"no walkable path from the core to throat <rect>"``
      * ``"no walkable floor in the core"``
      * ``"open seam at (x, y, z)"``
    """
    room_id: str
    ok: bool
    reason: str = ""


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
    # Corridor floor continuity (Requirement 5.2). Filled only when
    # ``validate(check_corridors=True)`` runs; empty otherwise. ``conflicts`` is
    # the list of corridor-id pairs whose walkable floors cross too close in Z
    # (design decision 12/16).
    corridors: List[CorridorResult] = field(default_factory=list)
    conflicts: List[Tuple[str, str]] = field(default_factory=list)
    checked_corridors: bool = False
    # Shaped rooms' verdicts (step 8); empty when no room has an Outline.
    outlines: List[OutlineResult] = field(default_factory=list)
    # The walk surface ``validate`` built, so the outline extractor can reuse it
    # (M2 Pipeline post-pass). Not serialised; ``None`` on other report paths.
    surface: Optional["WalkSurface"] = field(default=None, repr=False,
                                             compare=False)

    @property
    def passed(self) -> bool:
        return (self.total_rooms > 0 and self.reachable_rooms == self.total_rooms
                and all(o.ok for o in self.outlines))

    @property
    def corridors_passed(self) -> bool:
        """True when every corridor is connected and no pair conflicts.

        ``True`` when corridors were not checked, so a caller that doesn't ask
        for continuity sees no regression (umbrella Req 4.2 ``passed`` is
        unaffected).
        """
        if not self.checked_corridors:
            return True
        return all(c.connected for c in self.corridors) and not self.conflicts

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
        if self.checked_corridors:
            n_ok = sum(1 for c in self.corridors if c.connected)
            cstatus = "PASS" if self.corridors_passed else "FAIL"
            lines.append(
                f"  corridors: [{cstatus}] {n_ok}/{len(self.corridors)} continuous"
                + (f", {len(self.conflicts)} conflict(s)" if self.conflicts else "")
            )
            for c in self.corridors:
                if not c.connected:
                    lines.append(
                        f"    XX {c.corridor_id:<10} {c.from_room}->{c.to_room}"
                        f"  -> {c.reason}"
                    )
            for ci, cj in self.conflicts:
                lines.append(f"    !! {ci} conflicts with {cj}")
        for o in self.outlines:
            if not o.ok:
                lines.append(f"    XX outline {o.room_id:<10} -> {o.reason}")
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


def placed_models(eqg_path: str | Path) -> List["Placed"]:
    """Every ZON object the ``.eqg`` places with the model it places
    (``analyzer.footprints.placed_from_zon``), the terrain's own object left
    out. Empty when there is no archive at ``eqg_path`` (a test handing
    ``validate`` its own mesh), it has no ZON, or the ZON places only terrain."""
    from analyzer.footprints import placed_from_zon
    from core.zon import ZonFile

    if not Path(eqg_path).is_file():
        return []
    arc = PfsArchive.from_file(Path(eqg_path))
    zon_name = next((f for f in arc.list_files() if f.lower().endswith(".zon")), None)
    if zon_name is None:
        return []
    zon = ZonFile.from_bytes(arc.get(zon_name))
    wanted = {zon.models[o.model_id] for o in zon.objects}
    wanted = {f for f in wanted if not f.lower().endswith(".ter")}
    if not wanted:
        return []
    models = {f: TerFile.from_bytes(arc.get(f), name=f) for f in wanted if arc.get(f) is not None}
    return placed_from_zon(zon, models)


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
    # (F,) int: connected-component root (a standable face index) per standable
    # face; -1 for non-standable faces. Populated by ``build_walk_surface`` from
    # the union-find it keeps while wiring adjacency, so two standable faces are
    # in the same walkable component iff ``component[i] == component[j]``. This
    # is exactly the partition ``flood_reachable`` would recover, exposed once
    # instead of reflooded.
    component: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))


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


def build_walk_surface(ter: TerFile, agent: AgentModel, *,
                       skip_passable: bool = True,
                       floors_up: bool = True) -> WalkSurface:
    """
    Classify standable triangles and build walkable adjacency between them.

    A face is standable when it is a FLOOR: its winding normal points up within
    the walkable slope cap. A ceiling's underside (the same flat face wound the
    other way) is never standable, so a storey's ceiling can't pass as floor
    under the storey above (verticality task 18). Our builders wind floors up
    and ceilings down (``generators.geometry``; ``mapgeom`` reads floors the
    same way), and so does the EQG we write. ``floors_up=False`` is for meshes
    wound the other way, as the WLD loaders of the step 6/7 surveys read stock
    zones (floor normals point down there).

    Two standable faces are adjacent (the agent can walk between them) when
    their floors genuinely MEET: either they share a mesh vertex (an exact
    weld -- one 3D point, zero step), or their XY footprints actually touch (true
    triangle overlap, or an edge-to-edge gap within ``adjacency_eps`` by the real
    minimum XY distance) AND their interpolated floor heights AT THAT CONTACT
    POINT are within the step-up height. Comparing Z at the contact -- not at the
    two centroids -- and requiring true contact rather than a per-axis
    bounding-box clip is what keeps the gate sound: faces that merely overlap in
    XY while offset on the other axis, or stacked at different heights, do not
    connect.

    Polygons flagged ``FLAG_PASSABLE`` (non-collidable, e.g. a visual water
    plane) are never standable when ``skip_passable`` is set — the client walks
    through them. Generated dungeon/city meshes are all solid, so this leaves
    their results unchanged.
    """
    verts = np.array([[v.x, v.y, v.z] for v in ter.vertices], dtype=np.float64)
    faces = np.array([[p.v1, p.v2, p.v3] for p in ter.polygons], dtype=np.int64)

    if len(faces) == 0:
        return WalkSurface(verts, faces, np.zeros((0, 3)), np.zeros((0, 3)),
                           np.zeros(0, bool), {}, np.zeros(0, np.int64))

    a = verts[faces[:, 0]]
    b = verts[faces[:, 1]]
    c = verts[faces[:, 2]]
    raw_n = np.cross(b - a, c - a)
    lens = np.linalg.norm(raw_n, axis=1)
    safe = lens > 1e-9
    normals = np.zeros_like(raw_n)
    normals[safe] = raw_n[safe] / lens[safe, None]
    centroids = (a + b + c) / 3.0

    # Standable: a floor-wound face (normal up, or down for a WLD-wound mesh)
    # within the slope cap. A two-sided slab is floor on top (wound up) and
    # ceiling underneath (wound down): only its top is stood on.
    nz = normals[:, 2] if floors_up else -normals[:, 2]
    standable = safe & (nz >= agent.min_up_normal)
    if skip_passable:
        passable = np.array([bool(p.flags & FLAG_PASSABLE) for p in ter.polygons])
        standable &= ~passable

    std_idx = np.nonzero(standable)[0]

    # ---- Adjacency ----------------------------------------------------------
    # The walk surface is a graph whose nodes are standable faces; reachability
    # (``flood_reachable``) only cares about its CONNECTED COMPONENTS. So we keep
    # a union-find over standable faces alongside the adjacency lists: every
    # accepted edge is both recorded (so continuity floods can walk it) and
    # unioned (so the components stay current). The one thing the union-find buys
    # us for speed is a licence to DROP REDUNDANT EDGES -- an edge between two
    # faces already in the same component changes no component, so the expensive
    # seam contact test for such a pair can be skipped. Components, and therefore
    # ``flood_reachable`` from any face, are identical to the pre-speedup code;
    # only redundant seam edges are dropped (proved by M1-P4, task 2.3).
    #
    # Union-find indexed by POSITION in ``std_idx`` (0..S-1), not by face id, so
    # the parent/rank arrays stay small and dense.
    S = len(std_idx)
    pos_of = {int(fi): k for k, fi in enumerate(std_idx)}
    parent = np.arange(S, dtype=np.int64)
    rank = np.zeros(S, dtype=np.int64)

    def _find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        # Path compression.
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def _union(x: int, y: int) -> None:
        rx, ry = _find(x), _find(y)
        if rx == ry:
            return
        if rank[rx] < rank[ry]:
            rx, ry = ry, rx
        parent[ry] = rx
        if rank[rx] == rank[ry]:
            rank[rx] += 1

    # 1) Shared-vertex adjacency (cheap, exact mesh connectivity).
    vert_to_faces: Dict[int, List[int]] = {}
    for fi in std_idx:
        for vi in faces[fi]:
            vert_to_faces.setdefault(int(vi), []).append(int(fi))

    adjacency: Dict[int, set] = {int(fi): set() for fi in std_idx}

    # Two faces that share a mesh vertex (same index) meet EXACTLY at that
    # vertex in 3D -- they already agree in Z there (it is one point), so the
    # step across that seam is zero and they are walkably connected. This is the
    # vertex-based form of the step check: a welded seam has no step to clear,
    # so the old centroid-Z gate here was a spurious proxy that could wrongly
    # cut a legitimately-welded pair of standable faces. We keep this pass as the
    # exact mesh-connectivity backbone and drop the centroid test. Union as we go
    # so the seam pass can see the weld components already formed here.
    for vi, flist in vert_to_faces.items():
        f0 = flist[0]
        for k in range(1, len(flist)):
            fk = flist[k]
            adjacency[f0].add(fk)
            adjacency[fk].add(f0)
            # The star edges f0--fk above plus the all-pairs edges below are the
            # same undirected edge set the reference records (a vertex's faces
            # are a clique); recording the clique keeps the stored adjacency
            # byte-identical to the reference. The union only needs the star.
            _union(pos_of[f0], pos_of[fk])
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

    # Weld components after the shared-vertex pass. A seam edge can only MERGE
    # two faces that sit in DIFFERENT weld components (same-component pairs are
    # redundant and skipped below), and a merging edge requires true XY contact
    # within eps -- which forces the two faces' weld-component XY bounding boxes
    # to overlap within eps. So a face whose entire weld component's bbox is
    # isolated (touches no other component's bbox within eps) can never be an
    # endpoint of a component-changing edge, and is dropped from the seam
    # candidates. A terrain is a single weld component, so EVERY face is
    # isolated and the seam pass is empty (design: "a terrain is one weld
    # component, so its seam pass is empty").
    weld_root = np.array([_find(k) for k in range(S)], dtype=np.int64)
    comp_min: Dict[int, np.ndarray] = {}
    comp_max: Dict[int, np.ndarray] = {}
    for k, fi in enumerate(std_idx):
        r = int(weld_root[k])
        lo = fxy_min[fi]
        hi = fxy_max[fi]
        if r not in comp_min:
            comp_min[r] = lo.copy()
            comp_max[r] = hi.copy()
        else:
            np.minimum(comp_min[r], lo, out=comp_min[r])
            np.maximum(comp_max[r], hi, out=comp_max[r])

    roots = list(comp_min.keys())
    if len(roots) <= 1:
        # One weld component (e.g. terrain): nothing can merge. Seam pass empty.
        touches_other = {}
    else:
        rmin = np.array([comp_min[r] for r in roots])          # (C, 2)
        rmax = np.array([comp_max[r] for r in roots])          # (C, 2)
        touches_other = {}
        for ri, r in enumerate(roots):
            # bbox(r) within eps of bbox(other) on both axes, for any other.
            near = (
                (rmin[:, 0] - eps <= rmax[ri, 0]) & (rmax[:, 0] + eps >= rmin[ri, 0]) &
                (rmin[:, 1] - eps <= rmax[ri, 1]) & (rmax[:, 1] + eps >= rmin[ri, 1])
            )
            near[ri] = False
            touches_other[r] = bool(near.any())

    # Only faces in a component that touches another component feed the grid.
    if touches_other:
        seam_pos = np.array(
            [k for k in range(S) if touches_other.get(int(weld_root[k]), False)],
            dtype=np.int64,
        )
    else:
        seam_pos = np.zeros(0, np.int64)
    seam_faces = std_idx[seam_pos] if len(seam_pos) else np.zeros(0, np.int64)

    cell = max(eps * 4.0, 16.0)
    grid: Dict[Tuple[int, int], List[int]] = {}

    if len(seam_faces):
        # Vectorised cell ranges per face: floor((bbox +/- eps) / cell).
        lo_all = (fxy_min[seam_faces] - eps) / cell
        hi_all = (fxy_max[seam_faces] + eps) / cell
        c_lo = np.floor(lo_all).astype(np.int64)   # (n, 2)
        c_hi = np.floor(hi_all).astype(np.int64)   # (n, 2)
        for n, fi in enumerate(seam_faces):
            fi_i = int(fi)
            for cx in range(c_lo[n, 0], c_hi[n, 0] + 1):
                for cy in range(c_lo[n, 1], c_hi[n, 1] + 1):
                    grid.setdefault((cx, cy), []).append(fi_i)

    def _bbox_near(fi: int, fj: int) -> bool:
        # Cheap reject before the exact test: XY bounding boxes within eps.
        return (fxy_min[fi, 0] - eps <= fxy_max[fj, 0] and
                fxy_max[fi, 0] + eps >= fxy_min[fj, 0] and
                fxy_min[fi, 1] - eps <= fxy_max[fj, 1] and
                fxy_max[fi, 1] + eps >= fxy_min[fj, 1])

    seen_pairs: set = set()
    for key, flist in grid.items():
        if len(flist) < 2:
            # A cell holding a single face can produce no pair; skip it.
            continue
        # Skip a cell whose faces all share one weld component: every in-cell
        # pair is same-component (redundant) and would be skipped below anyway,
        # so the per-cell pair loop produces no edge. (Design: "skip the
        # per-cell pair loop for cells holding one component.")
        if len({int(weld_root[pos_of[f]]) for f in flist}) == 1:
            continue
        for i in range(len(flist)):
            for j in range(i + 1, len(flist)):
                fi, fj = flist[i], flist[j]
                if fj in adjacency[fi]:
                    continue
                # Redundant-edge skip: already in the same component, so this
                # edge (accepted or not) changes nothing. Skip BEFORE the
                # expensive contact test. This is the whole speed-up and it
                # cannot change components.
                if _find(pos_of[fi]) == _find(pos_of[fj]):
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
                    _union(pos_of[fi], pos_of[fj])

    adjacency_lists = {k: sorted(v) for k, v in adjacency.items()}

    # Component root per standable face (a face index), -1 elsewhere. Resolve to
    # the representative face id so callers can group faces by component without
    # re-flooding.
    component = np.full(len(faces), -1, dtype=np.int64)
    if S:
        roots_pos = np.array([_find(k) for k in range(S)], dtype=np.int64)
        component[std_idx] = std_idx[roots_pos]

    return WalkSurface(verts, faces, normals, centroids, standable,
                       adjacency_lists, component)


# ---------------------------------------------------------------------------
# Flood fill + room mapping
# ---------------------------------------------------------------------------

def _nearest_standable_face(surf: WalkSurface, point: np.ndarray,
                            xy_radius: float) -> Optional[int]:
    """
    Pick the standable face to start the walk from: the floor the player stands
    on at the safe point. The safe point is placed deliberately AT the entrance
    room centre (``entrance.center + (0, 0, 5)``), so the correct start face is
    the floor directly BENEATH it — the face whose XY projection CONTAINS the
    point — and, when several stacked faces contain it (a box dungeon where a
    corridor ramps up over the entrance floor), the one whose surface Z at that
    point is closest to the safe point's Z.

    The containment pass is what makes this correct on the elevation path. A
    plain "within ``xy_radius``, minimise |Δz|" rule (the historic behaviour,
    kept below only as a fallback) can prefer a DISTANT corridor face whose Z
    merely happens to sit nearer the safe point over the entrance's OWN floor
    directly under the safe point — stranding the whole flood on a tiny
    disconnected component and reporting every room unreachable even though the
    zone is fully connected from its real entrance floor (seed 2985, dungeon,
    26 rooms, dramatic: the entrance floor at z=0 floods to every room, but a
    ramp face ~370u away at z≈5.5 won the old |Δz| race against z=5 and reached
    almost nothing). Standing on the floor UNDER the spawn point, not the
    nearest-in-Z surface anywhere nearby, is the fix.
    """
    std_idx = np.nonzero(surf.standable)[0]
    if len(std_idx) == 0:
        return None

    # Preferred: the floor directly beneath the safe point — a face whose XY
    # projection contains it. Among those stacked faces, stand on the one whose
    # interpolated surface Z at the point is closest to the safe point's Z.
    containing: List[int] = []
    containing_z: List[float] = []
    for fi in std_idx:
        tri = surf.verts[surf.faces[fi]]
        if _point_in_tri_xy(point[0], point[1], tri):
            containing.append(int(fi))
            containing_z.append(_plane_z_at(tri, point[0], point[1]))
    if containing:
        dz = np.abs(np.asarray(containing_z) - point[2])
        return int(containing[int(np.argmin(dz))])

    # Fallback (no face underfoot — e.g. a safe point placed off any floor):
    # the nearest face in XY within the radius, breaking ties by |Δz|; failing
    # that, the globally nearest in XY.
    cen = surf.centroids[std_idx]
    dxy = np.linalg.norm(cen[:, :2] - point[:2], axis=1)
    within = dxy <= xy_radius
    cand = std_idx[within]
    if len(cand) == 0:
        return int(std_idx[int(np.argmin(dxy))])
    cz = surf.centroids[cand]
    dz = np.abs(cz[:, 2] - point[2])
    return int(cand[int(np.argmin(dz))])


def seed_face_for(surf: WalkSurface, safe_point) -> Optional[int]:
    """The standable face the walk starts from at ``safe_point`` — the
    validator's own choice (``validate`` uses the same 400 u radius)."""
    return _nearest_standable_face(surf, np.asarray(safe_point, dtype=np.float64), 400.0)


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


def _faces_in_room(surf: WalkSurface, room: RoomSpec,
                   rooms: Optional[List[RoomSpec]] = None) -> np.ndarray:
    """
    Indices of standable faces whose floor lies within the room footprint.

    The footprint test is primarily an XY question — "is there walkable floor
    under this room's area?". Z is used only to disambiguate when multiple
    walkable surfaces stack at the same XY (e.g. a box dungeon where a room's
    floor sits directly above/below another room's): we prefer the faces nearest
    the room's own floor height. For open terrain (outdoor/cave), the nominal
    ``floor_z`` won't match the undulating heightfield, so if the Z band selects
    nothing we fall back to all XY-matching faces — the terrain IS the floor.

    ``rooms`` (the spec's rooms) z-bounds that fallback for stacked builds
    (step 7): a room stacked over or under this one in plan is another storey,
    so the fallback keeps only faces between the nearest such room below
    (over its ceiling) and above (under its floor). The band test already
    picks a room's own floor when it was built; without the bound a room
    with no floor of its own would be "found" on the storey above or below.
    A layout without stacked rooms (no plan overlap) is unchanged.
    """
    (xmin, ymin, zmin), (xmax, ymax, zmax) = room.bounds
    std_idx = np.nonzero(surf.standable)[0]
    cen = surf.centroids[std_idx]

    in_xy = (
        (cen[:, 0] >= xmin) & (cen[:, 0] <= xmax) &
        (cen[:, 1] >= ymin) & (cen[:, 1] <= ymax)
    )
    if room.outline is not None:
        # A shaped room is only its Cells: floor in a corner of its Box is
        # something else's (step 8).
        hits = np.nonzero(in_xy)[0]
        in_xy[hits] = room.outline.contains(cen[hits, :2])
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
    # decides reachability), but none on a storey stacked above or below.
    lo, hi = _storey_band(room, rooms)
    if lo == -np.inf and hi == np.inf:
        return xy_idx
    return xy_idx[(xy_cen[:, 2] > lo) & (xy_cen[:, 2] < hi)]


def _storey_band(room: RoomSpec, rooms: Optional[List[RoomSpec]]):
    """``(lo, hi)``: the ceiling of the highest room under ``room`` and the
    floor of the lowest room over it, among the rooms overlapping it in plan
    (a stacked build's other storeys); infinite where there is none."""
    lo, hi = -np.inf, np.inf
    if not rooms:
        return lo, hi
    (x0, y0, z0), (x1, y1, z1) = room.bounds
    for r in rooms:
        if r.id == room.id:
            continue
        (rx0, ry0, rz0), (rx1, ry1, rz1) = r.bounds
        if min(x1, rx1) - max(x0, rx0) <= 1e-6 or min(y1, ry1) - max(y0, ry0) <= 1e-6:
            continue
        if rz1 <= z0:
            lo = max(lo, rz1)
        elif rz0 >= z1:
            hi = min(hi, rz0)
    return lo, hi


FLOOR_Z_TOL = 8.0


# ---------------------------------------------------------------------------
# Shaped rooms (step 8, Requirement 3)
# ---------------------------------------------------------------------------
#
# Everything outside a room still judges its Box, which is only stricter than its
# walls. These checks read the mesh inside the Box: every door leads through a
# Throat to the Core, nothing stands across a Throat, and the room is closed.

OUTLINE_TOL = 0.05    # how far a door, Throat or seam may be off (u)
THROAT_CLEAR = 0.5    # a wall only counts as across a Throat this far in: cut pieces can
                      # graze a Throat's corner by a hair, and a real one spans it (u)
BODY_RADIUS = 2.0     # how far a player's middle stays from a wall (u)
DOOR_STUB = 3.0       # a corridor's end can stand this far into its room (u)


def _door_strips(room: RoomSpec, spec: ZoneSpec):
    """Each door on ``room``'s walls: (side, c0, c1) as ``_door_openings`` finds it."""
    return [(side, c0, c1) for side, cuts in _door_openings(room, spec).items()
            for c0, c1, _top in cuts]


def _strip_in_throat(side: str, c0: float, c1: float, plane: float, t: Rect) -> bool:
    """Does the Throat ``t`` hold the door strip on the wall at ``plane``?"""
    tol = OUTLINE_TOL
    if side in ("N", "S"):
        return (t[0] <= c0 + tol and t[2] >= c1 - tol
                and t[1] <= plane + tol and t[3] >= plane - tol)
    return (t[1] <= c0 + tol and t[3] >= c1 - tol
            and t[0] <= plane + tol and t[2] >= plane - tol)


def _segment_hits_rect(p: np.ndarray, q: np.ndarray, r: Rect) -> bool:
    """Does the plan segment ``p``..``q`` enter the open rect ``r``? (Liang-Barsky)"""
    t0, t1 = 0.0, 1.0
    d = q - p
    for axis, lo, hi in ((0, r[0], r[2]), (1, r[1], r[3])):
        if abs(d[axis]) < 1e-12:
            if p[axis] <= lo or p[axis] >= hi:
                return False
            continue
        a, b = (lo - p[axis]) / d[axis], (hi - p[axis]) / d[axis]
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
        if t0 >= t1:
            return False
    return True


def _room_mesh_faces(surf: WalkSurface, room: RoomSpec) -> np.ndarray:
    """The faces wholly inside the room's Box."""
    (x0, y0, z0), (x1, y1, z1) = room.bounds
    tol = OUTLINE_TOL
    tri = surf.verts[surf.faces]
    inside = ((tri[:, :, 0] >= x0 - tol) & (tri[:, :, 0] <= x1 + tol)
              & (tri[:, :, 1] >= y0 - tol) & (tri[:, :, 1] <= y1 + tol)
              & (tri[:, :, 2] >= z0 - tol) & (tri[:, :, 2] <= z1 + tol))
    return np.nonzero(inside.all(axis=1))[0]


def _open_seam(surf: WalkSurface, room: RoomSpec, faces: np.ndarray, doors, slots):
    """A point on an edge only one face uses, away from every door and slot."""
    (x0, y0, _), (x1, y1, z1) = room.bounds
    planes = {"S": y0, "N": y1, "W": x0, "E": x1}
    tol = OUTLINE_TOL

    def allowed(a: np.ndarray, b: np.ndarray) -> bool:
        for side, c0, c1 in doors:
            axis, along = (1, 0) if side in ("N", "S") else (0, 1)
            if (abs(a[axis] - planes[side]) <= DOOR_STUB and abs(b[axis] - planes[side]) <= DOOR_STUB
                    and min(a[along], b[along]) >= c0 - tol and max(a[along], b[along]) <= c1 + tol):
                return True
        for s in slots:
            if (abs(a[2] - z1) <= tol and abs(b[2] - z1) <= tol
                    and min(a[0], b[0]) >= s[0] - tol and max(a[0], b[0]) <= s[2] + tol
                    and min(a[1], b[1]) >= s[1] - tol and max(a[1], b[1]) <= s[3] + tol):
                return True
        return False

    tri = surf.verts[surf.faces[faces]]
    keys = np.round(tri, 2)
    count: Dict[tuple, int] = {}
    ends: Dict[tuple, tuple] = {}
    for t, k in zip(tri, keys):
        for i in range(3):
            j = (i + 1) % 3
            a, b = tuple(k[i]), tuple(k[j])
            key = (a, b) if a < b else (b, a)
            count[key] = count.get(key, 0) + 1
            ends[key] = (t[i], t[j])
    for key in sorted(count):
        if count[key] == 1 and not allowed(*ends[key]):
            a, b = ends[key]
            mid = (a + b) / 2
            return f"({mid[0]:.1f}, {mid[1]:.1f}, {mid[2]:.1f})"
    return None


def check_outline(surf: WalkSurface, room: RoomSpec, spec: ZoneSpec,
                  agent: AgentModel) -> OutlineResult:
    """Judge one shaped room from the mesh (see ``OutlineResult``)."""
    outline = room.outline
    (x0, y0, z0), (x1, y1, z1) = room.bounds
    planes = {"S": y0, "N": y1, "W": x0, "E": x1}
    doors = _door_strips(room, spec) + list(outline.extra_doors)
    slots = _bridge_slots(room, spec)

    def fail(reason: str) -> OutlineResult:
        return OutlineResult(room.id, False, reason)

    def touching(a: Rect, b: Rect) -> bool:
        tol = OUTLINE_TOL
        return a[0] <= b[2] + tol and a[2] >= b[0] - tol and a[1] <= b[3] + tol and a[3] >= b[1] - tol

    # A Throat reaches the Core directly or through another Throat (an L's two legs).
    joined = [outline.core]
    waiting = list(outline.throats)
    while True:
        more = [t for t in waiting if any(touching(t, j) for j in joined)]
        if not more:
            break
        joined += more
        waiting = [t for t in waiting if t not in more]

    used = []
    for side, c0, c1 in doors:
        holding = [t for t in outline.throats if _strip_in_throat(side, c0, c1, planes[side], t)]
        if not holding:
            return fail(f"door without a throat at {side} {c0:.1f}..{c1:.1f}")
        used.extend(holding)
    if waiting:
        return fail(f"throat {tuple(round(v, 1) for v in waiting[0])} does not reach the core")

    # A wall across a Throat stands in it at body height. Any near-vertical face counts.
    faces = _room_mesh_faces(surf, room)
    body = z0 + agent.player_height / 2
    tri = surf.verts[surf.faces[faces]]
    nz = np.abs(surf.normals[faces, 2])
    tall = (nz < 0.7) & (tri[:, :, 2].min(axis=1) <= body) & (tri[:, :, 2].max(axis=1) >= body)
    # A room holding solids may have one in a Throat with a way round it; check_features
    # judges that, door to door.
    for t in () if room.features else outline.throats:
        shrunk = (t[0] + THROAT_CLEAR, t[1] + THROAT_CLEAR, t[2] - THROAT_CLEAR, t[3] - THROAT_CLEAR)
        for w in tri[tall]:
            pts = w[:, :2]
            d = np.linalg.norm(pts[:, None] - pts[None], axis=2)
            i, j = np.unravel_index(d.argmax(), d.shape)
            if _segment_hits_rect(pts[i], pts[j], shrunk):
                return fail(f"wall across throat {tuple(round(v, 1) for v in t)}")

    # The floor joins the Core to every Throat, on the room's own floor faces.
    own = _faces_in_room(surf, room, spec.rooms)
    if len(own) == 0:
        return fail("no walkable floor in the core")
    cen = surf.centroids[own]

    def faces_in(r: Rect) -> set:
        m = (cen[:, 0] >= r[0]) & (cen[:, 0] <= r[2]) & (cen[:, 1] >= r[1]) & (cen[:, 1] <= r[3])
        return {int(f) for f in own[m]}

    start = faces_in(outline.core)
    if not start:
        return fail("no walkable floor in the core")
    reached = _flood_subset(_local_adjacency(surf, agent, own), start)
    for t in outline.throats:
        if not faces_in(t) & reached:
            return fail(f"no walkable path from the core to throat {tuple(round(v, 1) for v in t)}")

    seam = _open_seam(surf, room, faces, doors, slots)
    if seam is not None:
        return fail(f"open seam at {seam}")
    return OutlineResult(room.id, True)


# ---- Features (step 9, Requirement 2) --------------------------------------
#
# A solid stands on an unbroken floor, so the walk surface alone thinks you can walk through
# it. These checks read walls from the mesh, not RoomSpec.features, so the gate doesn't
# take the generator's word: a plan grid over the room, each cell free if it's floor and
# a body's radius from every wall at body height.

CLEAR_CELL = 2.0      # the grid's cell (u)
TRANSITION_CLEAR_H = 2.0    # a Transition leaves this much clear width, in body heights
TRANSITION_HEAD_H = 2.0     # and this much headroom, in body heights
TRANSITION_HEAD = 8.0       # or in u, if more: the player is 6 u tall
TRANSITION_MARGIN = 3.0     # the gate walks this far past a Transition each way (u)
WALLED_OFF = 64.0     # a pocket of free floor this big, with no door, is walled off (u^2)


def _free_cells(surf: WalkSurface, room: RoomSpec, agent: AgentModel):
    """The room's plan grid: (x positions, y positions, free mask)."""
    (x0, y0, z0), (x1, y1, _z1) = room.bounds
    xs = np.arange(x0 + CLEAR_CELL / 2, x1, CLEAR_CELL)
    ys = np.arange(y0 + CLEAR_CELL / 2, y1, CLEAR_CELL)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    free = (room.outline.contains(np.c_[gx.ravel(), gy.ravel()]).reshape(gx.shape)
            if room.outline is not None else np.ones(gx.shape, bool))
    faces = _room_mesh_faces(surf, room)
    tri = surf.verts[surf.faces[faces]]
    nz = np.abs(surf.normals[faces, 2])
    body = z0 + agent.player_height / 2
    tall = (nz < 0.7) & (tri[:, :, 2].min(axis=1) <= body) & (tri[:, :, 2].max(axis=1) >= body)
    for w in tri[tall]:
        pts = w[:, :2]
        d = np.linalg.norm(pts[:, None] - pts[None], axis=2)
        i, j = np.unravel_index(d.argmax(), d.shape)
        a, b = pts[i], pts[j]
        ab = b - a
        t = np.clip(((gx - a[0]) * ab[0] + (gy - a[1]) * ab[1]) / max(float(ab @ ab), 1e-9), 0.0, 1.0)
        free &= np.hypot(gx - (a[0] + t * ab[0]), gy - (a[1] + t * ab[1])) >= BODY_RADIUS
    # The floor runs on under a solid, so inside one looks free. A solid shows by a cap: a
    # raised top inside the room, or an underside wound down at the floor's height.
    (_, _, _), (_, _, z1) = room.bounds
    zs = tri[:, :, 2]
    flat = nz > 0.9
    lifted = max(room.outline.lift) if room.outline is not None and room.outline.lift else 0.0
    raised = flat & (zs.min(axis=1) > z0 + lifted + 0.5) & (zs.max(axis=1) < z1 - 0.5) & (surf.normals[faces, 2] > 0)
    under = flat & (zs.max(axis=1) < z0 + 0.5) & (surf.normals[faces, 2] < 0)
    over = np.zeros(gx.shape, bool)     # raised floor: you can walk over it
    for cap, walkable in zip(tri[raised | under], raised[raised | under]):
        a, b, c = cap[:, :2]
        d0 = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d0) < 1e-9:
            continue
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / d0
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / d0
        inside = (l0 >= 0) & (l1 >= 0) & (l0 + l1 <= 1)
        free &= ~inside
        if walkable:
            over |= inside
    return xs, ys, free, over


def _door_cell(xs, ys, free, room: RoomSpec, door) -> Optional[Tuple[int, int]]:
    """The free cell nearest the middle of a door, just inside its wall."""
    side, c0, c1 = door
    (x0, y0, _), (x1, y1, _) = room.bounds
    mid = (c0 + c1) / 2
    px, py = {"N": (mid, y1), "S": (mid, y0), "E": (x1, mid), "W": (x0, mid)}[side]
    cand = np.argwhere(free)
    if len(cand) == 0:
        return None
    d = np.hypot(xs[cand[:, 0]] - px, ys[cand[:, 1]] - py)
    k = int(d.argmin())
    return (int(cand[k, 0]), int(cand[k, 1])) if d[k] <= (c1 - c0) / 2 + 2 * BODY_RADIUS + CLEAR_CELL else None


def check_features(surf: WalkSurface, room: RoomSpec, spec: ZoneSpec, agent: AgentModel) -> OutlineResult:
    """Judge a room holding Features or POIs from the mesh. ``reason`` is "" when it passes, or:

      * ``"door <side> <c0>..<c1> is blocked"``: no free floor at a door
      * ``"doors <a> and <b> are cut off from each other"``
      * ``"floor walled off at (x, y)"``: free floor no door can reach
      * ``"dais <n> can't be walked onto"``
      * ``"POI <purpose> can't be reached"``
    """
    def fail(reason: str) -> OutlineResult:
        return OutlineResult(room.id, False, reason)

    extra = list(room.outline.extra_doors) if room.outline is not None else []
    doors = _door_strips(room, spec) + extra
    xs, ys, free, over = _free_cells(surf, room, agent)
    labels, _n = label(free)
    door_labels = {}
    for door in doors:
        cell = _door_cell(xs, ys, free, room, door)
        side, c0, c1 = door
        name = f"{side} {c0:.1f}..{c1:.1f}"
        if cell is None:
            return fail(f"door {name} is blocked")
        door_labels[name] = labels[cell]
    names = sorted(door_labels)
    for other in names[1:]:
        if door_labels[other] != door_labels[names[0]]:
            return fail(f"doors {names[0]} and {other} are cut off from each other")
    if names:
        joined = door_labels[names[0]]
        # Inside a solid is a free pocket too, since the floor runs on under it. A pocket
        # counts as walled-off floor only if it reaches the room's own edge.
        room_cells = (room.outline.contains(np.c_[np.repeat(xs, len(ys)), np.tile(ys, len(xs))])
                      .reshape(len(xs), len(ys)) if room.outline is not None
                      else np.ones((len(xs), len(ys)), bool))
        outside = np.pad(~room_cells, 1, constant_values=True)
        near = binary_dilation(outside, iterations=int(BODY_RADIUS / CLEAR_CELL) + 1)[1:-1, 1:-1]
        # Floor behind a dais isn't walled off: you can walk over the dais to it.
        reach = int(np.ceil(BODY_RADIUS / CLEAR_CELL)) + 1
        whole, _m = label(free | (binary_dilation(over, iterations=reach) & room_cells)) if over.any() else (labels, 0)
        open_to_doors = {int(whole[c]) for c in np.argwhere(labels == joined).tolist() and
                         [tuple(np.argwhere(labels == joined)[0])]}
        # A nook of the room's own walls, too narrow for a body, is no Feature's doing: stock
        # caves have them. Judge only floor that a body could reach were the solids gone.
        body = binary_erosion(room_cells, iterations=reach) | free
        unsolid, _u = label(body)
        door_side = int(unsolid[tuple(np.argwhere(labels == joined)[0])])
        for k in range(1, int(labels.max()) + 1):
            if k == joined:
                continue
            cells = np.argwhere(labels == k)
            if int(whole[tuple(cells[0])]) in open_to_doors or int(unsolid[tuple(cells[0])]) != door_side:
                continue
            if len(cells) * CLEAR_CELL ** 2 >= WALLED_OFF and near[labels == k].any():
                x, y = xs[cells[:, 0]].mean(), ys[cells[:, 1]].mean()
                return fail(f"floor walled off at ({x:.1f}, {y:.1f})")

    # Standing on them: the room's walkable floor, flooded from where the doors are.
    (x0, y0, z0), (x1, y1, z1) = room.bounds
    std = np.nonzero(surf.standable)[0]
    cen = surf.centroids[std]
    own = std[(cen[:, 0] >= x0) & (cen[:, 0] <= x1) & (cen[:, 1] >= y0) & (cen[:, 1] <= y1)
              & (cen[:, 2] >= z0 - 1) & (cen[:, 2] <= z1)]
    if len(own) == 0:
        return fail("POI can't be reached") if room.pois else OutlineResult(room.id, True)
    low = own[surf.centroids[own, 2] <= z0 + agent.max_step_up / 2]
    reached = _flood_subset(_local_adjacency(surf, agent, own), {int(f) for f in low})

    def stands_at(x, y, z) -> bool:
        for f in reached:
            tri = surf.verts[surf.faces[f]]
            if _point_in_tri_xy(x, y, tri) and abs(_plane_z_at(tri, x, y) - z) <= agent.max_step_up:
                return True
        return False

    for k, feat in enumerate(room.features):
        if feat.kind == "dais":
            pts = np.array(feat.plan)
            mx, my = pts.mean(axis=0)
            if not stands_at(mx, my, z0 + feat.height):
                return fail(f"dais {k} can't be walked onto")
    for poi in room.pois:
        if not stands_at(poi.x, poi.y, poi.z):
            return fail(f"POI {poi.purpose} can't be reached")
    return OutlineResult(room.id, True)


def check_transition(surf: WalkSurface, cor: CorridorSpec, spec: ZoneSpec, agent: AgentModel) -> OutlineResult:
    """Judge a corridor's Transition from the mesh: walk through it. ``reason`` is "" when
    it passes, or:

      * ``"no floor through the <form>"``
      * ``"a step of <n> u through the <form>"``
      * ``"<form> leaves <n> u clear, under <m> u"``
      * ``"<form> leaves <n> u of headroom, under <m> u"``
      * ``"open seam at the <form> at (x, y, z)"``: an edge only one face uses
    """
    t = cor.transition

    def fail(reason: str) -> OutlineResult:
        return OutlineResult(cor.id, False, reason)

    h = body_height(spec.dungeon_race)
    least_clear, least_head = TRANSITION_CLEAR_H * h, max(TRANSITION_HEAD_H * h, TRANSITION_HEAD)
    axis, across = (0, 1) if t.along_x else (1, 0)
    line = (t.x, t.y)[axis]
    middle = (t.x, t.y)[across]
    reach = t.depth + TRANSITION_MARGIN
    half = cor.width / 2 + 1.0

    tri = surf.verts[surf.faces]
    lo, hi = tri.min(axis=1), tri.max(axis=1)
    near = ((hi[:, axis] >= line - reach - 1) & (lo[:, axis] <= line + reach + 1)
            & (hi[:, across] >= middle - half) & (lo[:, across] <= middle + half)
            & (hi[:, 2] >= t.z - reach) & (lo[:, 2] <= t.z + cor.height + reach))
    faces = np.nonzero(near)[0]
    tri, nz = tri[faces], surf.normals[faces, 2]
    standable = surf.standable[faces]

    def point(s: float) -> Tuple[float, float]:
        return (line + s, middle) if t.along_x else (middle, line + s)

    # Through it, down the middle: the floor, a step at a time. Floor with a solid's underside
    # resting on it is inside that solid, so the walker has to climb the solid's top instead.
    down = nz < -0.1
    samples = np.arange(-reach, reach + 0.5, 1.0)
    floor_z = []
    z = t.z
    for s in samples:
        x, y = point(float(s))
        heights = [_plane_z_at(f, x, y) for f, ok in zip(tri, standable) if ok and _point_in_tri_xy(x, y, f)]
        under = [_plane_z_at(f, x, y) for f in tri[down] if _point_in_tri_xy(x, y, f)]
        heights = [v for v in heights if v <= z + cor.height / 2 and not any(abs(u - v) < 0.5 for u in under)]
        if not heights:
            return fail(f"no floor through the {t.form}")
        best = min(heights, key=lambda v: abs(v - z))
        if abs(best - z) > agent.max_step_up and s > samples[0]:
            return fail(f"a step of {abs(best - z):.1f} u through the {t.form}")
        z = best
        floor_z.append(z)

    # Width and head are the Transition's own, within its depth: past it is the corridor's.
    own = [(s, z) for s, z in zip(samples, floor_z) if abs(s) <= t.depth + 1e-6] or         [min(zip(samples, floor_z), key=lambda sz: abs(sz[0]))]

    # At body height: how far a line across reaches each way from the middle before a wall.
    tall = np.abs(nz) < 0.7
    crossing = []
    for s, z in own:
        body = z + agent.player_height / 2
        ends = []
        for f in tri[tall & (tri[:, :, 2].min(axis=1) <= body) & (tri[:, :, 2].max(axis=1) >= body)]:
            pts = []
            for i in range(3):
                a, b = f[i], f[(i + 1) % 3]
                if (a[2] - body) * (b[2] - body) < 0 or a[2] == body:
                    pts.append(a + (b - a) * ((body - a[2]) / ((b[2] - a[2]) or 1.0)))
            if len(pts) >= 2:
                ends.append((pts[0][axis], pts[0][across], pts[1][axis], pts[1][across]))
        run = line + float(s)
        hits = []
        for a0, c0, a1, c1 in ends:
            if min(a0, a1) - 1e-6 <= run <= max(a0, a1) + 1e-6:
                hits.append(c0 if abs(a1 - a0) < 1e-9 else c0 + (c1 - c0) * (run - a0) / (a1 - a0))
                if abs(a1 - a0) < 1e-9:
                    hits.append(c1)
        left = max((c for c in hits if c <= middle + 1e-6), default=middle - half)
        right = min((c for c in hits if c >= middle - 1e-6), default=middle + half)
        crossing.append(right - left)
    clear = min(crossing)
    if clear < least_clear - 0.01:
        return fail(f"{t.form} leaves {clear:.1f} u clear, under {least_clear:.1f} u")

    # Overhead: the lowest surface over the floor.
    for s, z in own:
        x, y = point(float(s))
        over = [_plane_z_at(f, x, y) for f in tri[down] if _point_in_tri_xy(x, y, f)]
        over = [v for v in over if v > z + 1.0]
        if over and min(over) - z < least_head - 0.01:
            return fail(f"{t.form} leaves {min(over) - z:.1f} u of headroom, under {least_head:.1f} u")

    # Nothing open where the sections meet: an edge lying in the line itself has a face each
    # side of it. Off the line one-faced edges are normal, as a broken wall's foot on a floor.
    keys = np.round(tri, 2)
    count: Dict[tuple, int] = {}
    for k in keys:
        for i in range(3):
            a, b = tuple(k[i]), tuple(k[(i + 1) % 3])
            key = (a, b) if a < b else (b, a)
            count[key] = count.get(key, 0) + 1
    for (a, b), n in sorted(count.items()):
        if n == 1 and all(abs(p[axis] - line) <= OUTLINE_TOL and abs(p[across] - middle) <= cor.width / 2 + 0.5
                          for p in (a, b)):
            return fail(f"open seam at the {t.form} at ({a[0]:.1f}, {a[1]:.1f}, {a[2]:.1f})")
    return OutlineResult(cor.id, True)


def outline_checks(surf: WalkSurface, spec: ZoneSpec, agent: AgentModel) -> List[OutlineResult]:
    """Every shaped room's verdict, every room holding Features or POIs, and every corridor
    with a Transition; none for a build of plain empty Boxes."""
    out = [check_outline(surf, r, spec, agent) for r in spec.rooms if r.outline is not None]
    out += [check_features(surf, r, spec, agent) for r in spec.rooms if r.features or r.pois]
    out += [check_transition(surf, c, spec, agent) for c in spec.corridors if c.transition is not None]
    return out


# ---------------------------------------------------------------------------
# Corridor floor continuity (Requirement 5.2)
# ---------------------------------------------------------------------------
#
# ``validate`` answers "is every room reachable from the entrance?" by flooding
# the WHOLE walk surface. That is a weak oracle for a corridor: a corridor whose
# floor passes through a third room's footprint marks every room it touches as
# reachable, even though in the client the corridor is cut by that room's
# collidable walls (and the room by the corridor's). ``corridor_continuity``
# asks the stricter, local question for each corridor: *is there a walkable path
# from this corridor's own from-room floor to its own to-room floor, using only
# floor inside the corridor's route footprint and its two rooms — and NOT inside
# any other room?* A corridor that only "connects" by cutting through room C
# fails, because C's footprint is removed from the region.
#
# Design decision 15: the pruned walk surface (the union-find speed-up) keeps
# connected components but DROPS redundant seam edges, so flooding a small region
# across ``surf.adjacency`` could miss a seam the reference would have recorded.
# ``corridor_continuity`` therefore recomputes seam contacts LOCALLY among the
# region's standable faces (the region is small, so this is cheap) and never
# relies on the pruned adjacency lists. This is why M1-P4 (task 4.2) can assert
# that continuity results are identical on the optimised and reference surfaces.


def _room_footprint(room: RoomSpec) -> Rect:
    """The room's XY footprint as an axis-aligned rect ``(x0, y0, x1, y1)``."""
    (xmin, ymin, _), (xmax, ymax, _) = room.bounds
    return (xmin, ymin, xmax, ymax)


def _xy_in_rects(x: float, y: float, rects: List[Rect]) -> bool:
    """True when ``(x, y)`` lies inside (inclusive) any rect in ``rects``."""
    for x0, y0, x1, y1 in rects:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    return False


def _rects_overlap(a: Rect, b: Rect) -> bool:
    """True when two axis-aligned rects overlap (inclusive) in XY."""
    return (a[0] <= b[2] and a[2] >= b[0] and
            a[1] <= b[3] and a[3] >= b[1])


def _region_faces(surf: WalkSurface, include: List[Rect],
                  exclude: List[Rect],
                  exclude_outside_z: Optional[List[Tuple[Rect, float, float]]] = None,
                  ) -> np.ndarray:
    """Standable faces whose centroid XY is in ``include`` and not in ``exclude``.

    ``exclude_outside_z`` holds ``(rect, zlo, zhi)`` entries for rooms a Bridge
    crosses: a face in ``rect`` is dropped unless its centroid Z is within
    ``[zlo, zhi]`` (the deck's band), so the crossed room's own floor and
    ceiling leave the region while the deck through its air stays. ``None``
    (every caller but a bridge) is the historic test.
    """
    std_idx = np.nonzero(surf.standable)[0]
    if len(std_idx) == 0:
        return std_idx
    cen = surf.centroids[std_idx]
    keep = np.zeros(len(std_idx), dtype=bool)
    for k in range(len(std_idx)):
        x, y = float(cen[k, 0]), float(cen[k, 1])
        if _xy_in_rects(x, y, include) and not _xy_in_rects(x, y, exclude):
            if exclude_outside_z:
                z = float(cen[k, 2])
                if any(_xy_in_rects(x, y, [r]) and not (lo <= z <= hi)
                       for r, lo, hi in exclude_outside_z):
                    continue
            keep[k] = True
    return std_idx[keep]


def _local_adjacency(surf: WalkSurface, agent: AgentModel,
                     face_subset: np.ndarray) -> Dict[int, List[int]]:
    """Walkable adjacency among ``face_subset`` computed from scratch.

    Replays the two passes of ``build_walk_surface`` (shared mesh vertex, then
    XY footprint contact with a floor-height agreement test) but confined to
    ``face_subset`` and WITHOUT the union-find pruning that drops redundant seam
    edges. Confining the work to the region's handful of faces keeps this cheap;
    recomputing contacts (design decision 15) is what makes the flood immune to
    the speed-up having thrown away a seam between two faces already in the same
    global component.
    """
    subset = [int(f) for f in face_subset]
    if not subset:
        return {}
    subset_set = set(subset)
    adj: Dict[int, set] = {f: set() for f in subset}

    faces = surf.faces
    verts = surf.verts

    # 1) Shared-vertex adjacency within the subset.
    vert_to_faces: Dict[int, List[int]] = {}
    for fi in subset:
        for vi in faces[fi]:
            vert_to_faces.setdefault(int(vi), []).append(fi)
    for flist in vert_to_faces.values():
        for i in range(len(flist)):
            for j in range(i + 1, len(flist)):
                fi, fj = flist[i], flist[j]
                adj[fi].add(fj)
                adj[fj].add(fi)

    # 2) Footprint-contact adjacency across seams (true XY overlap / gap within
    #    adjacency_eps, floors agreeing in Z at the contact within max_step_up).
    eps = agent.adjacency_eps
    tris = {fi: np.stack([verts[faces[fi, 0]],
                          verts[faces[fi, 1]],
                          verts[faces[fi, 2]]], axis=0) for fi in subset}
    fxy_min = {fi: np.minimum.reduce(tris[fi][:, :2]) for fi in subset}
    fxy_max = {fi: np.maximum.reduce(tris[fi][:, :2]) for fi in subset}

    # Faces already joined can't change what a flood reaches, so their seam needn't be
    # worked out; a shaped room's many welded floor faces would otherwise cost seconds.
    parent = {f: f for f in subset}

    def find(f: int) -> int:
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    for fi, nbrs in adj.items():
        for fj in nbrs:
            parent[find(fi)] = find(fj)

    lo = np.array([fxy_min[f] for f in subset])
    hi = np.array([fxy_max[f] for f in subset])
    # Two faces whose heights never come within a step can't meet, wherever they touch.
    zlo = np.array([tris[f][:, 2].min() for f in subset])
    zhi = np.array([tris[f][:, 2].max() for f in subset])
    step = agent.max_step_up
    n = len(subset)
    for i in range(n):
        fi = subset[i]
        near = (((lo[i + 1:] - eps <= hi[i]) & (hi[i + 1:] + eps >= lo[i])).all(axis=1)
                & (zlo[i + 1:] <= zhi[i] + step) & (zhi[i + 1:] >= zlo[i] - step))
        for j in np.nonzero(near)[0] + i + 1:
            fj = subset[int(j)]
            if find(fi) == find(fj):
                continue
            dist, pt = _tri_tri_xy_contact(tris[fi], tris[fj])
            if pt is None or dist > eps:
                continue
            zi = _plane_z_at(tris[fi], pt[0], pt[1])
            zj = _plane_z_at(tris[fj], pt[0], pt[1])
            if abs(zi - zj) <= agent.max_step_up:
                adj[fi].add(fj)
                adj[fj].add(fi)
                parent[find(fi)] = find(fj)

    return {k: sorted(v) for k, v in adj.items() if k in subset_set}


def _flood_subset(adj: Dict[int, List[int]], start: set) -> set:
    """BFS across a local adjacency map from a set of start faces."""
    reached: set = set()
    stack = [f for f in start if f in adj]
    reached.update(stack)
    while stack:
        f = stack.pop()
        for nb in adj.get(f, ()):  # type: ignore[arg-type]
            if nb not in reached:
                reached.add(nb)
                stack.append(nb)
    return reached


def _route_penetration_span(route, rect: Rect) -> float:
    """Longest run of ``route``'s CENTRELINE inside ``rect`` (any leg).

    Liang-Barsky clip of each leg segment against the rectangle; the result is
    the clipped leg's length. Mirrors ``LayoutGenerator._resolve_crossings``'s
    ``_seg_enters_rect`` span measure EXACTLY, so the validator and the layout
    agree on what "the corridor cuts through this room" means.
    """
    best = 0.0
    wps = route.waypoints
    rx0, ry0, rx1, ry1 = rect
    for k in range(len(wps) - 1):
        (x0, y0), (x1, y1) = wps[k], wps[k + 1]
        dx, dy = x1 - x0, y1 - y0
        t0, t1 = 0.0, 1.0
        ok = True
        for p, q in ((-dx, x0 - rx0), (dx, rx1 - x0),
                     (-dy, y0 - ry0), (dy, ry1 - y0)):
            if abs(p) < 1e-9:
                if q < 0:
                    ok = False
                    break
                continue
            t = q / p
            if p < 0:
                if t > t1:
                    ok = False
                    break
                if t > t0:
                    t0 = t
            else:
                if t < t0:
                    ok = False
                    break
                if t < t1:
                    t1 = t
        if not ok or t1 <= t0:
            continue
        span = ((dx * (t1 - t0)) ** 2 + (dy * (t1 - t0)) ** 2) ** 0.5
        best = max(best, span)
    return best


def _genuinely_crossed_rooms(route, hw: float, spec: ZoneSpec,
                             cor: CorridorSpec, eps: float) -> List[str]:
    """Ids of rooms the corridor's CENTRELINE genuinely cuts through.

    "Genuinely" means the same bar ``LayoutGenerator._resolve_crossings`` uses
    to decide a route needs splitting: the centreline's clipped run inside the
    room (shrunk by ``eps`` so a leg merely running ALONG a wall face is not
    counted) exceeds one corridor width (``hw``). A corridor that only grazes a
    room's corner (span <= hw) is deliberately left unsplit by the layout, so
    the validator must NOT treat that graze as a crossing -- excluding such a
    room from the continuity region would sever the corridor's OWN floor where
    it legitimately runs beside the room (seed 8, dungeon, 30 rooms, dramatic,
    corr_5 grazing room_8 by ~23 u < hw 24.5: connected in the full mesh, but
    the old any-overlap exclusion cut its region and mislabelled it a crossing).
    """
    out: List[str] = []
    for r in spec.rooms:
        if r.id in (cor.from_room, cor.to_room):
            continue
        rfp = _room_footprint(r)
        shrunk = (rfp[0] + eps, rfp[1] + eps, rfp[2] - eps, rfp[3] - eps)
        if shrunk[0] > shrunk[2] or shrunk[1] > shrunk[3]:
            shrunk = rfp
        if _route_penetration_span(route, shrunk) > hw:
            out.append(r.id)
    return out


def corridor_continuity(surf: WalkSurface, spec: ZoneSpec,
                        agent: AgentModel) -> List[CorridorResult]:
    """Per-corridor floor-continuity verdicts (Requirement 5.2).

    For each corridor joining rooms A and B:

    1. ``region`` = the route footprint grown by ``agent.adjacency_eps`` ∪
       footprint(A) ∪ footprint(B), minus the footprint of every OTHER room.
    2. ``faces`` = standable faces whose centroid XY lies in ``region``.
    3. ``start`` = A's floor faces ∩ ``faces``; ``goal`` = B's floor faces ∩
       ``faces``.
    4. Flood from ``start`` across adjacency recomputed locally over ``faces``
       (design decision 15); ``connected`` iff start ≠ ∅, goal ≠ ∅ and the
       flood reaches a goal face.
    5. ``reason`` names the failure; a third-room crossing is reported as
       ``"crosses room <id>"``.

    The result does NOT include corridor–corridor conflicts; those are attached
    by :func:`corridor_conflicts` so the two checks stay independent.
    """
    rooms_by_id: Dict[str, RoomSpec] = {r.id: r for r in spec.rooms}
    results: List[CorridorResult] = []

    for cor in spec.corridors:
        a = rooms_by_id.get(cor.from_room)
        b = rooms_by_id.get(cor.to_room)
        if a is None or b is None:
            # A corridor to a point that isn't a room: no room floor to join.
            results.append(CorridorResult(
                cor.id, cor.from_room, cor.to_room, False,
                "no floor in from_room" if a is None else "no floor in to_room"))
            continue

        hw = cor.width / 2
        route = corridor_route(cor, rooms_by_id)
        leg_rects = route_footprint(route, hw + agent.adjacency_eps)
        fp_a = _room_footprint(a)
        fp_b = _room_footprint(b)
        include = leg_rects + [fp_a, fp_b]
        # A planned Switchback climbs in a stairwell beside its carry leg.
        lay = stair_layout(cor, rooms_by_id)
        if lay is not None and lay.stairwell is not None:
            e = agent.adjacency_eps
            x0, y0, x1, y1 = lay.stairwell
            include.append((x0 - e, y0 - e, x1 + e, y1 + e))
        # Exclude only the rooms the corridor's centreline GENUINELY cuts through
        # (span > hw) -- the same bar ``_resolve_crossings`` splits on. A room
        # the corridor merely grazes (span <= hw, left unsplit by the layout on
        # purpose) is NOT excluded, so subtracting it can't sever the corridor's
        # own floor where it legitimately runs beside that room.
        crossed_ids = set(_genuinely_crossed_rooms(
            route, hw, spec, cor, agent.adjacency_eps))
        # A Bridge: a crossed room the corridor passes through at height, in
        # its air (see ``bridged_rooms``). Only that room's floor and ceiling
        # leave the region; the deck over it stays. Empty for every corridor a
        # layout makes today, so the region below is the historic one.
        bridged = bridged_rooms(cor, crossed_ids, rooms_by_id, agent)
        # A crossed room the corridor passes wholly over or under, with the
        # Slab between (a stacked build's other storey, step 7), is not a
        # crossing, and its footprint stays in the region: its floor is far
        # from the corridor's floor and its ceiling is no floor at all, so the
        # flood can't step onto either, and the corridor's own rooms may lie
        # over or under it too. Any spec, stacked by a layout or not.
        stacked = stacked_rooms(cor, route, crossed_ids - bridged, rooms_by_id,
                                agent)
        exclude = [_room_footprint(r) for r in spec.rooms
                   if r.id not in (cor.from_room, cor.to_room)
                   and r.id in crossed_ids and r.id not in bridged
                   and r.id not in stacked]
        deck_band = None
        if bridged:
            lo = min(cor.from_z, cor.to_z) - agent.max_step_up
            hi = max(cor.from_z, cor.to_z) + agent.max_step_up
            deck_band = [(_room_footprint(rooms_by_id[rid]), lo, hi)
                         for rid in sorted(bridged)]

        region_faces = _region_faces(surf, include, exclude, deck_band)
        faces_set = {int(f) for f in region_faces}

        start = {int(f) for f in _faces_in_room(surf, a, spec.rooms)} & faces_set
        goal = {int(f) for f in _faces_in_room(surf, b, spec.rooms)} & faces_set

        connected = False
        reason = ""
        if not start:
            reason = "no floor in from_room"
        elif not goal:
            reason = "no floor in to_room"
        else:
            adj = _local_adjacency(surf, agent, region_faces)
            reached = _flood_subset(adj, start)
            if reached & goal:
                connected = True
            else:
                reason = "gap"

        # A third-room crossing is the more specific diagnosis when the route
        # GENUINELY cuts through another room (centreline span > hw -- the same
        # bar the layout splits on, so detection and prevention agree). A mere
        # corner graze is not a crossing and leaves the gap diagnosis in place.
        # It fails even when the flood found a way round: the corridor's walls
        # stand inside that room, whatever a stairwell beside the route lets
        # the flood do (seeds 7 and 8 at 30 rooms before task 12's fix).
        walled = crossed_ids - bridged - set(stacked)
        if walled:
            connected = False
            reason = f"crosses room {sorted(walled)[0]}"

        # A Vertical_Connector (a Staircase, or a Bridge) is walkable only if
        # its built floor also passes the connector check: risers, treads,
        # headroom and flush ends, read off the same mesh. The flood above
        # can't see a tread too short or a ceiling too low. Not run for flat
        # corridors and ramps, whose verdict stays the flood's alone.
        if (start and goal and not walled
                and (is_staircase(cor) or bridged)):
            chk = check_connector(surf, cor, rooms_by_id, agent,
                                  route=route, bridged=bridged)
            if not chk.ok:
                connected = False
                reason = chk.reason

        results.append(CorridorResult(
            cor.id, cor.from_room, cor.to_room, connected, reason))

    return results


def _route_floor_z_at(route, cor: CorridorSpec, x: float, y: float,
                      lay=None) -> float:
    """Expected floor height of ``cor``'s own tube at the XY point ``(x, y)``.

    For a planned stair, ``lay`` (its ``stair_layout``) gives the walk path
    and the pitch line: the height is the profile at the nearest point of the
    route walked through the stair (``_walk_path``), so a compact flight's
    level approaches and a switchback's stairwell read at their real heights.

    Mirrors the geometry builder's carry-leg rule (``MeshBuilder._emit_route``):
    the entire rise is confined to leg ``carry`` (defaulting to the longest leg),
    every leg before it sits flat at ``from_z`` and every leg after at ``to_z``.
    We find the route leg whose segment is nearest ``(x, y)`` in XY and return
    that leg's floor height, interpolating along the carry leg. This lets
    :func:`_corridor_floor_z` tell this corridor's own floor apart from a second
    corridor crossing its footprint at a different height.
    """
    if lay is not None and not lay.cramped:
        pts, cum, s_off = _walk_path(route, lay)
        best_d, best_s = float("inf"), 0.0
        for k in range(len(pts) - 1):
            (ax, ay), (bx, by) = pts[k], pts[k + 1]
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            t = 0.0 if seg2 <= 1e-12 else max(0.0, min(1.0, (
                (x - ax) * dx + (y - ay) * dy) / seg2))
            d = (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2
            if d < best_d:
                best_d, best_s = d, cum[k] + t * (cum[k + 1] - cum[k])
        return float(_profile_z(lay, best_s - s_off))
    wps = route.waypoints
    n_legs = len(wps) - 1
    if n_legs <= 0:
        return float(cor.from_z)
    carry = route.carry
    if carry is None or carry < 0:
        # Builder default: the longest leg carries the rise.
        def _leg_len(k: int) -> float:
            (ax, ay), (bx, by) = wps[k], wps[k + 1]
            return abs(bx - ax) + abs(by - ay)
        carry = max(range(n_legs), key=_leg_len)

    # Per-waypoint floor heights: from_z up to the carry leg, to_z after it.
    zs = [cor.from_z if i <= carry else cor.to_z for i in range(len(wps))]

    # Nearest leg to (x, y); interpolate within that leg by arc fraction.
    best_d = float("inf")
    best_z = float(cor.from_z)
    for k in range(n_legs):
        ax, ay = wps[k]
        bx, by = wps[k + 1]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-12:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / seg2))
        px, py = ax + t * dx, ay + t * dy
        d = (x - px) ** 2 + (y - py) ** 2
        if d < best_d:
            best_d = d
            best_z = zs[k] + t * (zs[k + 1] - zs[k])
    return float(best_z)


def _corridor_floor_z(surf: WalkSurface, cor: CorridorSpec,
                      agent: AgentModel,
                      rooms: Optional[Mapping[str, "RoomSpec"]] = None,
                      ) -> Dict[Tuple[int, int], List[float]]:
    """Bucket a corridor's OWN walkable floor heights by a coarse XY grid cell.

    The region is the corridor's own route footprint (no room footprints, so two
    corridors are compared only where their TUBES overlap, not where they share a
    room). Returns ``{(cx, cy): [z, …]}`` keyed by a floor-cell index, so two
    corridors can be compared cell-by-cell over the XY intersection.

    Crucially, the region footprint is an XY test, so where a SECOND corridor
    crosses this one it drops its own floor faces into this corridor's
    footprint too. Keeping those would merge the two corridors' Z ranges and
    make every overlapping pair "conflict" regardless of how far apart they
    sit in Z — defeating design decision 16's clearance exemption. So we keep
    only faces that belong to THIS corridor's own tube: a face whose centroid
    Z lies within the tube (from its expected floor at that XY up to the
    floor + the corridor's height, with ``max_step_up`` slack). A crossing
    corridor passing over (above the ceiling) or under (below the floor) is
    excluded, so a pair separated by at least the clearance shares no floor in
    any cell and is correctly NOT a conflict.
    """
    hw = cor.width / 2
    # Plan the route exactly as the MESH was built: MeshBuilder.add_corridor
    # calls ``corridor_route(cor, {r.id: r for r in spec.rooms})``, so the exit
    # axis (hence a Z-corridor's jog position, hence the whole XY footprint)
    # is decided by the rooms' footprint separation. Planning with an EMPTY map
    # falls back to the endpoint-delta basis, which for a Z-corridor can pick
    # the OTHER primary axis and place the jog in a different column — a
    # footprint that no longer matches the built tube. That mismatch made the
    # gate flag pairs whose real tubes never touch (false-positive conflicts,
    # confirmed on the flat sweep: the mesh floors share zero XY cells). Pass
    # the real rooms so the gate measures the geometry that was actually built.
    route = corridor_route(cor, rooms if rooms is not None else {})
    rects = route_footprint(route, hw)
    lay = stair_layout(cor, rooms if rooms is not None else {})
    if lay is not None and lay.stairwell is not None:
        rects = rects + [lay.stairwell]
    faces = _region_faces(surf, rects, [])
    cell = max(agent.adjacency_eps * 4.0, 16.0)
    slack = agent.max_step_up
    buckets: Dict[Tuple[int, int], List[float]] = {}
    for f in faces:
        c = surf.centroids[f]
        floor_z = _route_floor_z_at(route, cor, float(c[0]), float(c[1]),
                                    lay)
        # Only this corridor's own tube: floor (minus a step) up through the
        # clearance (plus a step). Crossing corridors at a separated height fall
        # outside this band and are dropped.
        if not (floor_z - slack <= c[2] <= floor_z + cor.height + slack):
            continue
        key = (int(math.floor(c[0] / cell)), int(math.floor(c[1] / cell)))
        buckets.setdefault(key, []).append(float(c[2]))
    return buckets


def corridor_conflicts(surf: WalkSurface, spec: ZoneSpec,
                       agent: AgentModel) -> List[Tuple[str, str]]:
    """Pairs of corridors whose walkable floors cross too close in Z.

    Design decision 12: two corridors that SHARE NO ROOM conflict when their
    route footprints intersect in XY AND their walkable floors over the
    intersection are closer in Z than the clearance. Floors only: a tube's
    ceiling is wound down, so it is not on the walk surface (task 18).
    Decision 16: clearance is the lower corridor's ``height`` + 1 u (the box
    backend models no ceiling thickness), never less than
    ``agent.player_height``; a pair separated by at least the clearance is NOT
    a conflict — so a future open **bridge** kind that spans over another
    corridor at a separated height is exempt by construction,
    not by a special case.

    Returns a sorted list of conflicting ``(corridor_id, corridor_id)`` pairs
    (ids ordered within each pair).
    """
    corridors = list(spec.corridors)
    rooms = {r.id: r for r in spec.rooms}
    buckets = [_corridor_floor_z(surf, c, agent, rooms) for c in corridors]
    pairs: List[Tuple[str, str]] = []

    for i in range(len(corridors)):
        ci = corridors[i]
        for j in range(i + 1, len(corridors)):
            cj = corridors[j]
            # Corridors that share a room are allowed to meet (they join there).
            if {ci.from_room, ci.to_room} & {cj.from_room, cj.to_room}:
                continue
            bi, bj = buckets[i], buckets[j]
            # Clearance: the lower corridor's clearance height + 1 u, floored at
            # the player's height. Use the smaller of the two corridor heights.
            clearance = max(min(ci.height, cj.height) + 1.0, agent.player_height)
            conflict = False
            for key, zi_list in bi.items():
                zj_list = bj.get(key)
                if not zj_list:
                    continue
                # Floors over this shared cell: any pair within the clearance is
                # a conflict (tubes too close to pass one over the other).
                zi_min, zi_max = min(zi_list), max(zi_list)
                zj_min, zj_max = min(zj_list), max(zj_list)
                gap = max(zi_min - zj_max, zj_min - zi_max, 0.0)
                if gap < clearance:
                    conflict = True
                    break
            if conflict:
                pair = (ci.id, cj.id) if ci.id <= cj.id else (cj.id, ci.id)
                pairs.append(pair)

    return sorted(set(pairs))


# ---------------------------------------------------------------------------
# Vertical connectors: Staircases and Bridges (verticality step 7, Req 2)
# ---------------------------------------------------------------------------
#
# The flood above joins two floor faces when they touch within
# ``adjacency_eps`` and their heights agree within ``max_step_up``. That is
# exactly the riser rule, but it is blind to two things a stair needs: a tread
# long enough to stand on, and a ceiling high enough to walk under. So a
# connector gets a second, stricter look at the same mesh: a walk along the
# corridor's centreline (``check_connector``), reading the floor under each
# point, every riser it climbs, the tread between risers and the ceiling over
# the floor. The spec-level oracle (``classify_corridor``) predicts the same
# verdict from the corridor's numbers; the two are built to agree:
#
#   * a riser is a jump in floor height where the floor is discontinuous; the
#     oracle's riser is ``|to_z - from_z| / steps`` (the builder's).
#   * a tread is the run between two risers; the oracle's is the built carry
#     leg's length / ``steps`` (the builder pulls a leg back by half a width at
#     a bend; ``_built_leg`` mirrors it).
#   * headroom is the lowest ceiling over the floor; the builder's ceiling
#     follows the treads, so it is the corridor height, less one riser when
#     the stair descends along the axis it is built on.
#   * a landing is where the flight meets flat floor: a room's doorway or a
#     bend. A break there that isn't the stair's own riser is a gap.
#
# The failure classes, in the order a reason lists them. Each detail follows
# its class name after a colon; several classes are joined with "; ".
STAIR_FAILURES = ("gap at landing", "riser too tall", "tread too short",
                  "no headroom", "gap in flight", "too steep")
BRIDGE_FAILURES = ("gap at bridge end", "gap in bridge deck",
                   "bridge deck too steep", "no headroom")

# A floor jump smaller than this is a lip, not a riser: it makes no tread.
RISER_MIN = 0.1
# A riser at a landing that differs from the stair's own riser by more than
# this is a landing mismatch, not the stair's riser.
LANDING_TOL = 0.05
# Centreline sample spacing (u) for the connector walk; finer for fine treads.
PROFILE_STEP = 0.1
# How far the connector walk starts and ends inside each room's floor.
PROFILE_INSET = 4.0


def is_staircase(cor: CorridorSpec) -> bool:
    """True when the builder makes treads and risers for ``cor``: ``steps``
    > 0 and a height change (``_add_straight_leg``'s own condition), or a
    planned stair (``steps == AUTO_STAIRS``, ``generators.geometry``)."""
    return bool(cor.steps and cor.steps > 0
                and abs(cor.to_z - cor.from_z) > 0.01) or is_auto_stair(cor)


def _planned(cor: CorridorSpec, rooms):
    """How the gate judges ``cor``: ``(cor, layout)``. A planned stair gives
    its ``stair_layout`` (the one the builder built from); a cramped one,
    built as the hand-count stair stretched over its leg, is judged as that
    stair (``steps`` = its risers, no layout). Any other corridor comes back
    as it is, with no layout."""
    lay = stair_layout(cor, rooms or {})
    if lay is None:
        return cor, None
    if lay.cramped:
        return replace(cor, steps=lay.plan.risers), None
    return cor, lay


def _walk_path(route, lay):
    """The route walked through a planned stair: the legs before the carry
    leg, the stair's ``path``, the legs after. Returns (points, arc lengths,
    arc length of ``lay.path[0]``)."""
    wps = list(route.waypoints)
    k = lay.carry
    raw = wps[:k + 1] + list(lay.path) + wps[k + 2:]
    mark = k + 1                       # lay.path[0] in raw
    pts, off = [], 0
    for i, p in enumerate(raw):
        dup = bool(pts) and abs(p[0] - pts[-1][0]) + abs(p[1] - pts[-1][1]) < 1e-9
        if not dup:
            pts.append((float(p[0]), float(p[1])))
        if i == mark:
            off = len(pts) - 1
    cum = [0.0]
    for p, q in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
    return pts, cum, cum[off]


def _profile_z(lay, s):
    """The planned stair's pitch line at arc length ``s`` along its path
    (level at from_z before it, at to_z after)."""
    xs, zs = zip(*lay.profile)
    return np.interp(s, xs, zs)


def bridged_rooms(cor: CorridorSpec, crossed_ids, rooms: Mapping[str, RoomSpec],
                  agent: AgentModel) -> set:
    """The rooms ``cor`` crosses as a Bridge: through the room's air.

    A crossed room (the route genuinely cuts its footprint) is bridged when
    the corridor's floor stays at least a player's height above the room's
    floor and a player's height below its ceiling, all the way: the deck is
    in the room's volume, clear of its floor (a player under it) and of its
    ceiling (a player on it). A corridor crossing a room at the room's own
    floor is the "crosses room" failure, as before.

    A built Bridge (task 11: ``cor.bridge`` names the room and
    ``geometry.bridge_layout`` places it) runs over the room's ceiling, which
    is cut open under the deck: that room is bridged when the deck is at
    least a player's height over its floor (the shaft over the slot is the
    deck's headroom, which the connector walk measures).
    """
    out = set()
    lo = min(cor.from_z, cor.to_z)
    hi = max(cor.from_z, cor.to_z)
    built = None
    if cor.bridge and cor.bridge in crossed_ids:
        built = bridge_layout(cor, rooms)
    for rid in crossed_ids:
        r = rooms.get(rid)
        if r is None:
            continue
        if built is not None and rid == built.room:
            if min(built.z0, built.z1, lo) >= r.floor_z + agent.player_height:
                out.add(rid)
            continue
        if (lo >= r.floor_z + agent.player_height
                and hi + agent.player_height <= r.floor_z + r.height):
            out.add(rid)
    return out


def stacked_rooms(cor: CorridorSpec, route, crossed_ids,
                  rooms: Mapping[str, RoomSpec], agent: AgentModel
                  ) -> Dict[str, Tuple[float, float]]:
    """The crossed rooms ``cor`` passes wholly over or under (a stacked
    build's other storeys, step 7), each with the corridor's floor band over
    it: ``{room id: (lowest floor, highest floor)}``. The band is taken over
    the route's legs whose footprint overlaps the room (the carry leg spans
    its whole rise); the corridor's tube (floor to floor + height) must lie
    under the room's floor or over its ceiling, with the Slab between, all
    along it (the layout's rule, ``LayoutGenerator._z_clear``). Closer than
    the Slab, the corridor runs through the room's roof or floor: the
    "crosses room" failure."""
    from generators.topology.embed import SLAB
    out: Dict[str, Tuple[float, float]] = {}
    if not crossed_ids:
        return out
    wps = list(route.waypoints)
    zs, _ = MeshBuilder._waypoint_zs(wps, None if route.carry < 0 else route.carry,
                                     cor.from_z, cor.to_z)
    hw = cor.width / 2
    for rid in crossed_ids:
        r = rooms.get(rid)
        if r is None:
            continue
        fp = _room_footprint(r)
        lo, hi = np.inf, -np.inf
        for k in range(len(wps) - 1):
            (x0, y0), (x1, y1) = wps[k], wps[k + 1]
            leg = (min(x0, x1) - hw, min(y0, y1) - hw, max(x0, x1) + hw, max(y0, y1) + hw)
            if (min(leg[2], fp[2]) - max(leg[0], fp[0]) > 1e-6
                    and min(leg[3], fp[3]) - max(leg[1], fp[1]) > 1e-6):
                lo, hi = min(lo, zs[k], zs[k + 1]), max(hi, zs[k], zs[k + 1])
        if lo > hi:
            continue
        if (hi + cor.height + SLAB <= r.floor_z + 1e-6
                or lo >= r.floor_z + r.height + SLAB - 1e-6):
            out[rid] = (float(lo), float(hi))
    return out


def _resolve_carry(route) -> int:
    """The leg carrying the rise (the builder's rule: -1 → the longest)."""
    wps = route.waypoints
    n = len(wps) - 1
    if route.carry is not None and route.carry >= 0:
        return route.carry
    return max(range(n), key=lambda k: abs(wps[k + 1][0] - wps[k][0])
               + abs(wps[k + 1][1] - wps[k][1]))


def _built_leg(route, k: int, hw: float, rising: bool):
    """Leg ``k``'s built span as ``(t0, t1)`` distances from its start
    waypoint, or None. Mirrors ``MeshBuilder._leg_ends``: a leg ending at a
    bend is pulled back ``hw`` to the bend square; a rising leg too short for
    that is built whole."""
    wps = route.waypoints
    n = len(wps) - 1
    (x0, y0), (x1, y1) = wps[k], wps[k + 1]
    length = abs(x1 - x0) + abs(y1 - y0)
    t0 = hw if k > 0 else 0.0
    t1 = hw if k < n - 1 else 0.0
    if length - t0 - t1 <= 1e-6:
        if length > 1e-6 and rising:
            return 0.0, length
        return None
    return t0, length - t1


@dataclass
class _Flight:
    """A staircase's flight as the builder makes it."""
    carry: int
    n_legs: int
    length: float          # built carry-leg length
    up_coord: bool         # the carry leg runs toward higher X/Y in route order
    a_z: float             # builder's tread-0 height (low-coordinate end)
    b_z: float             # builder's landing height (high-coordinate end)


def _flight_of(cor: CorridorSpec, route) -> _Flight:
    wps = route.waypoints
    n = len(wps) - 1
    carry = _resolve_carry(route)
    span = _built_leg(route, carry, cor.width / 2,
                      abs(cor.to_z - cor.from_z) > 0.01)
    length = 0.0 if span is None else span[1] - span[0]
    (x0, y0), (x1, y1) = wps[carry], wps[carry + 1]
    up = (x1 - x0) + (y1 - y0) > 0
    a_z, b_z = (cor.from_z, cor.to_z) if up else (cor.to_z, cor.from_z)
    return _Flight(carry, n, length, up, a_z, b_z)


def _order(failures: List[Tuple[str, str]], classes) -> str:
    """One reason string: each class once (its first detail), in ``classes``
    order."""
    first: Dict[str, str] = {}
    for cls, detail in failures:
        first.setdefault(cls, detail)
    return "; ".join(f"{c}: {first[c]}" for c in classes if c in first)


def _stair_failures_spec(corr: CorridorSpec, agent: AgentModel,
                         rooms: Optional[Mapping[str, RoomSpec]]
                         ) -> List[Tuple[str, str]]:
    """The spec-level staircase verdict: (class, detail) per failure."""
    rooms = rooms or {}
    corr, lay = _planned(corr, rooms)
    route = corridor_route(corr, rooms)
    fl = _flight_of(corr, route)
    dz = abs(corr.to_z - corr.from_z)
    # A planned stair: its own riser and tread, every riser on the leg (none
    # at a doorway), and the ceiling following its pitch line.
    n = lay.plan.risers if lay is not None else corr.steps
    r = lay.plan.riser if lay is not None else dz / corr.steps
    out: List[Tuple[str, str]] = []

    # Landings: each doorway must meet its room's floor. A room the corridor
    # names but whose wall the doorway misses by more than the seam tolerance
    # is a hole; a floor height off by more than the step-up (after the
    # stair's own riser, when the flight's top riser is at that door) is a
    # step nobody climbs.
    for end in ("from", "to"):
        room = rooms.get(corr.from_room if end == "from" else corr.to_room)
        if room is None:
            continue
        ex, ey, ez = ((corr.from_x, corr.from_y, corr.from_z) if end == "from"
                      else (corr.to_x, corr.to_y, corr.to_z))
        (rx0, ry0, _), (rx1, ry1, _) = room.bounds
        miss = math.hypot(max(rx0 - ex, 0.0, ex - rx1),
                          max(ry0 - ey, 0.0, ey - ry1))
        if miss > agent.adjacency_eps:
            out.append(("gap at landing",
                        f"{end} doorway {miss:.1f}u short of {room.id}"))
            continue
        off = room.floor_z - ez
        if abs(off) <= LANDING_TOL:
            continue
        jump = off
        touches = (fl.carry == 0) if end == "from" else (fl.carry == fl.n_legs - 1)
        # The builder's last riser stands at the flight's high-coordinate end.
        riser_here = (lay is None and touches
                      and (fl.up_coord if end == "to" else not fl.up_coord))
        if riser_here:
            jump = off + (fl.b_z - fl.a_z) / corr.steps
        if abs(jump) > agent.max_step_up:
            out.append(("gap at landing",
                        f"{abs(jump):.1f}u step onto {room.id}'s floor exceeds "
                        f"step-up {agent.max_step_up:.1f}u"))

    if r > agent.max_step_up:
        out.append(("riser too tall",
                    f"stair step ~{r:.1f}u exceeds step-up "
                    f"{agent.max_step_up:.1f}u (too tall to climb)"))
    if n >= 2 and r >= RISER_MIN:
        tread = lay.plan.tread if lay is not None else fl.length / corr.steps
        if tread < agent.min_tread:
            out.append(("tread too short",
                        f"tread {tread:.2f}u under {agent.min_tread:.1f}u"))
    descends = (corr.to_z < corr.from_z) if lay is not None else fl.b_z < fl.a_z
    headroom = corr.height - (r if descends else 0.0)
    if headroom < agent.player_height:
        out.append(("no headroom",
                    f"{headroom:.1f}u over a tread under player height "
                    f"{agent.player_height:.0f}u"))
    return out


@dataclass
class ConnectorCheck:
    """The mesh-level verdict on one Vertical_Connector (``check_connector``).

    ``risers`` are the signed floor jumps the centreline walk climbed, in route
    order; ``treads`` the runs between consecutive risers on the flight;
    ``min_headroom`` the lowest ceiling over the corridor's floor (``inf`` when
    open to the sky). ``reason`` lists each failure class once, in the order
    of ``STAIR_FAILURES`` / ``BRIDGE_FAILURES``.
    """
    corridor_id: str
    kind: str                      # "stair" | "bridge"
    ok: bool
    reason: str = ""
    risers: List[float] = field(default_factory=list)
    treads: List[float] = field(default_factory=list)
    min_headroom: float = math.inf


def _bary_z(P: np.ndarray, T: np.ndarray):
    """Points ``P`` (N, 2) against triangles ``T`` (M, 3, 3): (inside, z),
    each (N, M) — XY containment (edges inclusive) and the plane height."""
    ax, ay, az = T[:, 0, 0], T[:, 0, 1], T[:, 0, 2]
    bx, by, bz = T[:, 1, 0], T[:, 1, 1], T[:, 1, 2]
    cx, cy, cz = T[:, 2, 0], T[:, 2, 1], T[:, 2, 2]
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    ok = np.abs(det) > 1e-12
    det = np.where(ok, det, 1.0)
    px = P[:, 0:1]
    py = P[:, 1:2]
    l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
    l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
    l3 = 1.0 - l1 - l2
    tol = 1e-7
    inside = ok & (l1 >= -tol) & (l2 >= -tol) & (l3 >= -tol)
    z = l1 * az + l2 * bz + l3 * cz
    return inside, z


def check_connector(surf: WalkSurface, cor: CorridorSpec,
                    rooms: Mapping[str, RoomSpec], agent: AgentModel, *,
                    route=None, bridged: Optional[set] = None) -> ConnectorCheck:
    """Walk a Staircase or Bridge along its centreline on the built mesh.

    The walk runs from ``PROFILE_INSET`` inside the from-room's floor, along
    the corridor's route, to the same distance inside the to-room. At each
    point it stands on the floor-wound face (normal up, within the slope cap)
    nearest the floor it stood on before, among the faces near the height the
    spec intends there (within one riser plus the step-up: a lower room's
    floor under a bridge is not this corridor's floor). It records:

    * a **riser** wherever the floor jumps (located exactly by bisection);
      one taller than the step-up fails. On the flight it is "riser too tall";
      at a landing, unless it is the stair's own riser, "gap at landing".
    * a **hole** wherever no floor is underfoot for longer than
      ``adjacency_eps`` (the walk's seam tolerance): "gap at landing" (or
      "gap in flight" between two treads; "too steep" when the floor there is
      a face over the slope cap). For a Bridge, a hole or step before or
      after the bridged rooms is "gap at bridge end", over them "gap in bridge
      deck".
    * the **tread** between consecutive risers on the flight; one shorter than
      ``agent.min_tread`` is "tread too short".
    * the **headroom**: the lowest ceiling-wound face over the floor, along the
      corridor (not inside the rooms); under ``agent.player_height`` is "no
      headroom".

    Winding is the floor/ceiling test: the box backend winds floors up and
    ceilings down (the walk surface's standable faces are the floors).
    """
    rooms = rooms or {}
    if route is None:
        route = corridor_route(cor, rooms)
    bridged = set(bridged or ())
    stair = is_staircase(cor)
    kind = "stair" if stair else "bridge"
    hw = cor.width / 2
    # A planned stair is walked along its own path, against its pitch line.
    cor, lay = _planned(cor, rooms) if stair else (cor, None)
    if not stair:
        rise = 0.0
    elif lay is not None:
        rise = lay.plan.riser
    else:
        rise = abs(cor.to_z - cor.from_z) / cor.steps

    # ---- the path: route waypoints, extended into each room ---------------
    if lay is not None:
        walk_pts, _, s_lay = _walk_path(route, lay)
        wps = [np.asarray(p, dtype=np.float64) for p in walk_pts]
    else:
        wps = [np.asarray(p, dtype=np.float64) for p in route.waypoints]

    def _unit(d):
        n = float(np.hypot(d[0], d[1]))
        return d / n if n > 1e-9 else None

    d0 = next((u for u in (_unit(wps[i] - wps[i + 1])
                           for i in range(len(wps) - 1)) if u is not None), None)
    d1 = next((u for u in (_unit(wps[i + 1] - wps[i])
                           for i in reversed(range(len(wps) - 1))) if u is not None),
              None)
    if d0 is None or d1 is None:
        return ConnectorCheck(cor.id, kind, False,
                              "gap at landing: corridor has no length")
    pts = [wps[0] + d0 * PROFILE_INSET] + wps + [wps[-1] + d1 * PROFILE_INSET]
    seg = np.array([float(np.hypot(*(pts[i + 1] - pts[i])))
                    for i in range(len(pts) - 1)])
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(cum[-1])
    pts_a = np.array(pts)

    def point_at(s):
        s = np.atleast_1d(np.asarray(s, dtype=np.float64))
        i = np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(seg) - 1)
        t = np.where(seg[i] > 1e-12, (s - cum[i]) / np.where(seg[i] > 1e-12,
                                                            seg[i], 1.0), 0.0)
        return pts_a[i] + (pts_a[i + 1] - pts_a[i]) * t[:, None]

    # Arc position of waypoint k is cum[k + 1] (pts[0] is the room inset).
    if lay is not None:
        # The flights run from the profile's first rise to its last.
        s0 = float(cum[1]) + s_lay
        f0 = s0 + lay.profile[1][0]
        f1 = s0 + lay.profile[-2][0]
    else:
        carry = _resolve_carry(route)
        span = _built_leg(route, carry, hw, abs(cor.to_z - cor.from_z) > 0.01)
        if span is None:
            f0 = f1 = float(cum[carry + 1])
        else:
            f0 = float(cum[carry + 1]) + span[0]
            f1 = float(cum[carry + 1]) + span[1]

    def expected_z(s):
        s = np.asarray(s, dtype=np.float64)
        if lay is not None:
            return _profile_z(lay, s - s0)
        if f1 - f0 <= 1e-9:
            return np.where(s <= f0, cor.from_z, cor.to_z)
        t = np.clip((s - f0) / (f1 - f0), 0.0, 1.0)
        return cor.from_z + (cor.to_z - cor.from_z) * t

    band = rise + agent.max_step_up + 1e-6
    slope_rate = math.tan(math.radians(agent.walkable_slope_deg))

    # ---- the faces near the path -------------------------------------------
    margin = hw + agent.adjacency_eps + 1.0
    pmin = pts_a.min(axis=0) - margin
    pmax = pts_a.max(axis=0) + margin
    tris_all = surf.verts[surf.faces] if len(surf.faces) else np.zeros((0, 3, 3))
    if len(tris_all):
        tmin = tris_all[:, :, :2].min(axis=1)
        tmax = tris_all[:, :, :2].max(axis=1)
        near = ((tmax[:, 0] >= pmin[0]) & (tmin[:, 0] <= pmax[0]) &
                (tmax[:, 1] >= pmin[1]) & (tmin[:, 1] <= pmax[1]))
    else:
        near = np.zeros(0, bool)
    nz = surf.normals[:, 2] if len(surf.faces) else np.zeros(0)
    floor_m = near & surf.standable & (nz > 1e-9)
    steep_m = near & ~surf.standable & (nz > 1e-6)
    ceil_m = near & (nz < -1e-6)
    T_floor = tris_all[floor_m]
    T_steep = tris_all[steep_m]
    T_ceil = tris_all[ceil_m]

    def floors_at(s: float) -> np.ndarray:
        """Floor heights in the band at arc position ``s``."""
        if not len(T_floor):
            return np.zeros(0)
        P = point_at(s)
        ins, z = _bary_z(P, T_floor)
        ze = float(expected_z(s))
        m = ins[0] & (np.abs(z[0] - ze) <= band)
        return z[0][m]

    def continues(s: float, s_ref: float, z_ref: float) -> bool:
        """Is the floor at ``s`` a continuous surface from (s_ref, z_ref)?"""
        c = floors_at(s)
        return bool(len(c)) and bool(
            np.any(np.abs(c - z_ref) <= slope_rate * abs(s - s_ref) + 1e-3))

    def edge(s_in: float, s_out: float, z_ref: float) -> float:
        """Bisect the edge of the surface holding (s_in, z_ref): ``s_in`` is on
        it, ``s_out`` is not. Returns the last position still on it."""
        lo, hi = s_in, s_out
        for _ in range(40):
            m = (lo + hi) / 2
            if continues(m, s_in, z_ref):
                lo = m
            else:
                hi = m
        return lo

    # ---- sample the floor along the path -----------------------------------
    ds = PROFILE_STEP
    if lay is not None:
        ds = max(0.01, min(ds, lay.plan.tread / 4))
    elif stair and f1 - f0 > 1e-9:
        ds = max(0.01, min(ds, (f1 - f0) / cor.steps / 4))
    S = np.linspace(0.0, total, max(2, int(math.ceil(total / ds)) + 1))
    ds = float(S[1] - S[0])
    jump_thr = slope_rate * ds + 1e-3
    zexp = expected_z(S)

    cand: List[np.ndarray] = []
    steep_at = np.zeros(len(S), bool)
    chunk = max(1, 2_000_000 // max(1, len(T_floor) + len(T_steep)))
    for c0 in range(0, len(S), chunk):
        P = point_at(S[c0:c0 + chunk])
        ze = zexp[c0:c0 + chunk, None]
        if len(T_floor):
            ins, z = _bary_z(P, T_floor)
            m = ins & (np.abs(z - ze) <= band)
            cand.extend(z[k][m[k]] for k in range(len(P)))
        else:
            cand.extend(np.zeros(0) for _ in range(len(P)))
        if len(T_steep):
            ins, z = _bary_z(P, T_steep)
            steep_at[c0:c0 + chunk] = np.any(
                ins & (np.abs(z - ze) <= band + agent.player_height), axis=1)

    floor_z = np.full(len(S), np.nan)
    risers: List[Tuple[float, float, float]] = []  # (pos, signed rise, floor before)
    breaks: List[Tuple[str, float, float, str]] = []  # (what, s0, s1, detail)
    prev_k: Optional[int] = None                # last sample with floor
    hole_k: Optional[int] = None                # first sample of current hole
    steep_in_hole = False
    for k in range(len(S)):
        c = cand[k]
        if len(c):
            ref = floor_z[prev_k] if prev_k is not None else float(zexp[k])
            z = float(c[int(np.argmin(np.abs(c - ref)))])
        else:
            z = None
        if z is None:
            if hole_k is None:
                hole_k = k
                steep_in_hole = False
            steep_in_hole = steep_in_hole or bool(steep_at[k])
            continue
        floor_z[k] = z
        if prev_k is None:
            if hole_k is not None:       # no floor where the walk starts
                right = S[k] if k == 0 else edge(S[k], S[hole_k], z)
                breaks.append(("hole", 0.0, right,
                               f"{right:.1f}u without floor"))
        elif hole_k is not None:
            zl = float(floor_z[prev_k])
            left = edge(S[prev_k], S[hole_k], zl)
            right = edge(S[k], S[k - 1], z)
            gap = right - left
            dz = z - zl
            if gap > agent.adjacency_eps:
                what = "steep" if steep_in_hole else "hole"
                breaks.append((what, left, right,
                               f"{gap:.1f}u without floor"
                               if what == "hole" else
                               f"{gap:.1f}u of floor over the "
                               f"{agent.walkable_slope_deg:.0f}deg cap"))
            elif abs(dz) >= RISER_MIN:
                risers.append(((left + right) / 2, dz, zl))
        else:
            zl = float(floor_z[prev_k])
            dz = z - zl
            if abs(dz) > jump_thr:
                pos = edge(S[prev_k], S[k], zl)
                if abs(dz) >= RISER_MIN:
                    risers.append((pos, dz, zl))
        prev_k = k
        hole_k = None
    if hole_k is not None:                       # no floor where the walk ends
        left = 0.0 if prev_k is None else edge(S[prev_k], S[hole_k],
                                               float(floor_z[prev_k]))
        breaks.append(("hole", left, total, f"{total - left:.1f}u without floor"))

    # ---- headroom along the corridor (not inside the rooms) ----------------
    min_head = math.inf
    head_pts = [(float(S[k]), float(floor_z[k])) for k in range(len(S))
                if not np.isnan(floor_z[k])]
    for pos, dz, zl in risers:   # both sides of each riser: a tread's ends
        head_pts.append((pos - 1e-6, zl))
        head_pts.append((pos + 1e-6, zl + dz))
    head_pts = [(s, z) for s, z in head_pts
                if PROFILE_INSET - 1e-9 <= s <= total - PROFILE_INSET + 1e-9]
    head_at = 0.0
    if head_pts and len(T_ceil):
        hs = np.array([p[0] for p in head_pts])
        hz = np.array([p[1] for p in head_pts])
        chunk = max(1, 2_000_000 // len(T_ceil))
        for c0 in range(0, len(hs), chunk):
            ins, z = _bary_z(point_at(hs[c0:c0 + chunk]), T_ceil)
            above = ins & (z > hz[c0:c0 + chunk, None] + 1e-6)
            room = np.where(above, z - hz[c0:c0 + chunk, None], np.inf).min(axis=1)
            k = int(np.argmin(room))
            if room[k] < min_head:
                min_head = float(room[k])
                head_at = float(hs[c0 + k])

    # ---- verdict -------------------------------------------------------------
    failures: List[Tuple[str, str]] = []
    tol = 1e-3
    step = agent.max_step_up
    flight_risers = sorted(p for p, _, _ in risers if f0 - tol <= p <= f1 + tol)
    treads = [float(b - a) for a, b in zip(flight_risers, flight_risers[1:])]

    if stair:
        for pos, dz, _ in risers:
            if abs(dz) <= step:
                continue
            interior = f0 + tol < pos < f1 - tol
            own = abs(abs(dz) - rise) <= LANDING_TOL
            on_flight = f0 - tol <= pos <= f1 + tol
            if interior or (on_flight and own):
                failures.append(("riser too tall",
                                 f"stair step ~{abs(dz):.1f}u exceeds step-up "
                                 f"{step:.1f}u (too tall to climb)"))
            else:
                failures.append(("gap at landing",
                                 f"{abs(dz):.1f}u step at the landing exceeds "
                                 f"step-up {step:.1f}u"))
        for what, s0, s1, detail in breaks:
            if what == "steep":
                failures.append(("too steep", detail))
            elif f0 + tol < s0 and s1 < f1 - tol:
                failures.append(("gap in flight", detail))
            else:
                failures.append(("gap at landing", detail))
        if treads and min(treads) < agent.min_tread:
            failures.append(("tread too short",
                             f"tread {min(treads):.2f}u under "
                             f"{agent.min_tread:.1f}u"))
        classes = STAIR_FAILURES
    else:
        inb = []
        for rid in bridged:
            r = rooms.get(rid)
            if r is None:
                continue
            (x0, y0, _), (x1, y1, _) = r.bounds
            P = point_at(S)
            m = ((P[:, 0] >= x0) & (P[:, 0] <= x1) &
                 (P[:, 1] >= y0) & (P[:, 1] <= y1))
            if m.any():
                inb.extend([float(S[m].min()), float(S[m].max())])
        b0, b1 = (min(inb), max(inb)) if inb else (f0, f1)

        def where(s0, s1):
            if s1 <= b0:
                return "gap at bridge end", f" ({cor.from_room} end)"
            if s0 >= b1:
                return "gap at bridge end", f" ({cor.to_room} end)"
            return "gap in bridge deck", ""

        for pos, dz, _ in risers:
            if abs(dz) > step:
                cls, at = where(pos, pos)
                failures.append((cls, f"{abs(dz):.1f}u step exceeds step-up "
                                      f"{step:.1f}u{at}"))
        for what, s0, s1, detail in breaks:
            if what == "steep":
                failures.append(("bridge deck too steep", detail))
            else:
                cls, at = where(s0, s1)
                failures.append((cls, detail + at))
        classes = BRIDGE_FAILURES

    if min_head < agent.player_height:
        failures.append(("no headroom",
                         f"{min_head:.1f}u over the floor at {head_at:.1f}u "
                         f"along, under player height "
                         f"{agent.player_height:.0f}u"))

    reason = _order(failures, classes)
    return ConnectorCheck(cor.id, kind, not failures, reason,
                          risers=[dz for _, dz, _ in sorted(risers)],
                          treads=treads, min_headroom=min_head)


def classify_corridor(corr: CorridorSpec, agent: AgentModel,
                      rooms: Optional[Mapping[str, RoomSpec]] = None
                      ) -> Tuple[bool, str]:
    """
    Judge a corridor's intended geometry against the agent, from the spec alone.

    Returns (walkable, reason). This is the "why" oracle: when a room is
    unreachable and the corridor that should serve it is itself a cliff ramp or
    an oversized staircase, we can name that precisely instead of a generic gap.
    A flat/shallow corridor returns walkable=True (so the break is elsewhere —
    a true mesh disconnect).

    A Staircase (``steps > 0``) is judged as the builder will make it, the
    verdict ``check_connector`` reaches on the built mesh: "riser too tall"
    (riser over the step-up), "tread too short" (built flight / steps under
    ``agent.min_tread``), "no headroom" (corridor height, less a riser where the
    ceiling descends over a tread, under the player's height) and, given
    ``rooms``, "gap at landing" (a doorway off its room's wall, or a floor step
    onto the room over the step-up). Each class is listed once, in
    ``STAIR_FAILURES`` order. Without ``rooms`` the route is planned from the
    endpoints alone, as the builder does for a corridor naming no rooms.
    """
    dz = abs(corr.to_z - corr.from_z)
    run = math.hypot(corr.to_x - corr.from_x, corr.to_y - corr.from_y)
    if dz < 1e-3:
        return True, "flat"
    if is_staircase(corr):
        judged, lay = _planned(corr, rooms)
        step = lay.plan.riser if lay is not None else dz / judged.steps
        failures = _stair_failures_spec(corr, agent, rooms)
        if failures:
            return False, _order(failures, STAIR_FAILURES)
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
    rooms = {r.id: r for r in spec.rooms}
    for c in spec.corridors:
        ends = {c.from_room, c.to_room}
        if room_id not in ends:
            continue
        other = (ends - {room_id}).pop() if len(ends) == 2 else ""
        # Rooms only matter to a staircase's landings; a ramp or flat
        # corridor's verdict is the historic one.
        walkable, why = classify_corridor(c, agent, rooms)
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
             agent: Optional[AgentModel] = None,
             check_corridors: bool = False,
             *,
             bowl: Optional[BowlGateParams] = None,
             placed: Optional[Sequence["Placed"]] = None) -> TraversalReport:
    """
    Load the mesh and room graph, walk the mesh from the safe point, and report
    per-room reachability.

    When ``check_corridors`` is True, also fill ``report.corridors`` (per-corridor
    floor continuity, Requirement 5.2) and ``report.conflicts`` (corridor pairs
    that cross too close in Z, design decision 12), and set
    ``report.checked_corridors``. ``report.passed`` keeps its umbrella Req 4.2
    meaning (every room reachable) regardless; ``report.corridors_passed``
    reflects the extra checks (and is ``True`` when they were not run).

    ``bowl`` is the defaulted wilderness bowl-gate parameter set (keyword-only).
    **When it is ``None`` — the dungeon/city path — this function behaves
    EXACTLY as it always has: the Spawn flood seeds from the spec's safe point,
    reachability is reported over the whole walk surface, and the returned
    ``TraversalReport`` is unchanged (no regression).** When supplied, it carries
    the playable mask, the exterior off-map bands, and an optional Spawn-point
    override that the bowl invariant (task 10.2) consumes; task 10.1 only threads
    the parameters through (flood seed + the reachable set are exposed on the
    report for 10.2 to test) and does not yet compute a bowl pass/fail verdict.

    Placed models (room-decor task 5): the ZON objects the ``.eqg`` places, or
    ``placed`` when given, are judged from their own collidable triangles as
    obstacles beside the mesh's (``analyzer.footprints.check_room_props``).
    Each failure is one more failed entry in ``report.outlines``, its
    ``room_id`` the room it's in. With no placed model in the room graph the
    report is exactly what it was without this check.
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
        surface=surf,
    )

    # Flood seed. The dungeon/city path (``bowl is None``) uses the spec's safe
    # point EXACTLY as before — no behaviour change. A wilderness build may hand
    # the bowl gate a Spawn point to seed from instead; when it doesn't, the
    # safe point is used, so even a supplied ``bowl`` without a spawn_point keeps
    # the historic seed.
    if bowl is not None and bowl.spawn_point is not None:
        safe = np.array(bowl.spawn_point, dtype=np.float64)
    else:
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
        if check_corridors:
            report.checked_corridors = True
            for cor in spec.corridors:
                report.corridors.append(CorridorResult(
                    cor.id, cor.from_room, cor.to_room, False,
                    "no floor in from_room"))
        return report

    reachable = flood_reachable(surf, seed_face)
    report.reachable_faces = len(reachable)

    # First pass: determine reachability per room (needed before graph diagnosis,
    # which asks "is this unreachable room adjacent to a reachable one?").
    room_faces_by_id: Dict[str, np.ndarray] = {}
    reached_by_id: Dict[str, List[int]] = {}
    for room in spec.rooms:
        rf = _faces_in_room(surf, room, spec.rooms)
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

    report.outlines = outline_checks(surf, spec, agent)
    if placed is None:
        placed = placed_models(eqg_path)
    if placed:
        from analyzer.footprints import check_room_props, collidable_triangles

        for f in check_room_props(surf, reachable, spec, placed, collidable_triangles(ter),
                                  seed_face, agent):
            report.outlines.append(OutlineResult(f.where or "props", False, str(f)))

    if check_corridors:
        report.checked_corridors = True
        results = corridor_continuity(surf, spec, agent)
        conflicts = corridor_conflicts(surf, spec, agent)
        report.conflicts = conflicts
        # Attach the conflict reason to each corridor in a conflicting pair
        # (design decision 16). A corridor can already carry a continuity reason;
        # the conflict reason only replaces an empty one so continuity diagnoses
        # aren't lost. ``corridors_passed`` fails on either count regardless.
        conflict_partner: Dict[str, str] = {}
        for ci, cj in conflicts:
            conflict_partner.setdefault(ci, cj)
            conflict_partner.setdefault(cj, ci)
        for cr in results:
            if cr.corridor_id in conflict_partner and not cr.reason:
                cr.reason = f"conflicts with corridor {conflict_partner[cr.corridor_id]}"
        report.corridors = results

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
    parser.add_argument("--check-corridors", action="store_true",
                        help="Also report per-corridor floor continuity and "
                             "corridor-corridor conflicts (Requirement 5.2)")
    args = parser.parse_args()

    eqg = _resolve_eqg(args.zone, args.output)
    agent = AgentModel(walkable_slope_deg=args.slope_cap, max_step_up=args.step_up)

    spec_path = args.spec
    if spec_path is None and eqg.suffix.lower() == ".eqg":
        spec_path = eqg.with_suffix(".json")

    try:
        rep = validate(eqg, spec_path=spec_path, agent=agent,
                       check_corridors=args.check_corridors)
    except Exception as e:  # noqa: BLE001 - CLI boundary, show a clean message
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

    print(rep.summary())
    sys.exit(0 if rep.passed else 1)
