"""
generators/wilderness/bowl.py
-----------------------------
Bowl assembly (roadmap step 1, wave 4). This is the FIRST stage that turns the
synthesized heightfield (:class:`~generators.wilderness.synth.SynthResult`) into
the *bowl* a player can actually be sealed inside: the Rim is realized on the
fine TER heightfield per each declared ``Edge_Connection``, interior ``lava``
becomes an impassable damaging hazard, and the region/barrier metadata that the
wave-5 ``.zone.json`` sidecar will carry is COLLECTED here (not wired).

Two tasks land together in this one file because both author the one new module
and both emit ``RegionSpec``s that flow to EQG:

* **task 9.2 — Realize the Rim per Edge_Connection** (Req 3.4/3.5/3.6/3.7, 13.1)
    - ``mountain`` (Req 3.4): the perimeter rim band is raised so the inner face
      of the band is a slope STEEPER than ``AgentModel.walkable_slope_deg`` (~40°,
      the ``min_up_normal`` threshold in ``analyzer/traverse.py``). The geometry
      ITSELF seals the edge — the agent classifies those faces as non-standable.
      Collision truth is the slope; **no barrier record** is emitted.
    - ``river`` (Req 3.5 / 13.1): the boundary water edge already sits at
      ``Water_Level`` (frozen by the matrix/synth). Water is visual-only (Req
      13.1, no collision volume), so an **Invisible_Wall** ``RegionSpec`` —
      emitted ``generic`` → ``APV`` and flagged in the sidecar metadata — is what
      actually stops the player at that edge.
    - ``zoneline`` (Req 3.6): the flat walkable gap leading off-map is emitted as
      a ``RegionSpec(kind="zoneline")`` (→ ``ATP``), held flat (Req 8.4, done in
      synth) and reachable from Spawn (Req 4.5, proved by the wave-4 gate).
    - Every Edge_Connection type and every Invisible_Wall barrier is COLLECTED as
      region metadata for the sidecar (Req 3.7). The sidecar WIRING is wave 5;
      here we only return the metadata.

* **task 9.3 — interior lava as an impassable, damaging hazard** (Req 10.1/10.2/10.3)
    - ``lava`` cells become impassable interior terrain: a
      ``RegionSpec(kind="lava")`` (→ ``ALV``) PLUS heightfield the agent rejects
      (a steep spike, not walkable floor) so the built-mesh flood does not cross
      it (Req 10.1). Every lava region is recorded in the collected metadata
      flagged **damaging** (Req 10.2). ``lava`` is an interior hazard ONLY and is
      never offered as an Edge_Connection type (Req 10.3) — this module reads lava
      from interior cells, never from the Rim.

Z is up (EverQuest convention). The fine grid maps cell ``(i, j)`` to world XY
``(origin_x + (i + 0.5) * resolution, origin_y + (j + 0.5) * resolution)``.

This stage does NOT wire the sidecar, does NOT touch ``analyzer/traverse.py``
(the built-mesh bowl gate is task 10, extending traverse concurrently), and does
NOT build the TER mesh (the backend does that downstream). It operates on the
``SynthResult`` arrays and the governing :class:`DesignMatrix`, returning a
:class:`BowlResult` the downstream ``ZoneSpec`` assembly consumes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy is pinned
    np = None  # type: ignore

from analyzer.traverse import (
    AgentModel,
    OffMapBand,
    build_walk_surface,
    flood_reachable,
    reached_off_map_segments,
)
from core.ter import MAGIC_TERRAIN, Material, Polygon, TerFile, Vertex
from generators.wilderness.matrix import DesignMatrix
from generators.wilderness.synth import SynthResult
from generators.zone_spec import RegionSpec

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

#: Multiple of the walkable per-cell rise used to seal a ``mountain`` edge by
#: slope (Req 3.4). The agent stands on a face only when its gradient is at or
#: below ``tan(walkable_slope_deg)`` — i.e. a per-cell rise at or below
#: ``tan(slope_cap) * resolution``. Raising the rim band's inner face to this
#: MULTIPLE of that limit guarantees the inner slope is well past the cap, so the
#: agent classifies every rim face as non-standable and the flood stops at the
#: ridge. 2.5x leaves generous headroom above the cap while keeping the raise
#: bounded (the frozen ridge target is already ~400 u; this only steepens the
#: INNER transition, never lowers the ridge).
MOUNTAIN_SEAL_SLOPE_FACTOR: float = 2.5

#: Height (world units) a ``lava`` cell is spiked to ABOVE its local
#: neighbourhood so the per-triangle agent rejects it as non-walkable floor (Req
#: 10.1). The spike makes the lava-cell faces steep (gradient past the slope cap)
#: AND steps them beyond ``max_step_up`` from the surrounding plains, so the
#: walkable flood cannot enter or cross the lava region. This is a COLLISION
#: barrier on the interior terrain; the ``ALV`` region + damaging flag carry the
#: runtime hazard semantics separately.
LAVA_SPIKE_HEIGHT: float = 60.0

#: Half-extent padding (world units) added around a region's cell footprint when
#: emitting its ``RegionSpec`` volume, so the region box comfortably covers the
#: cells it represents.
REGION_EXTENT_PAD: float = 0.0

#: Region volume half-height (world units) for the emitted ``RegionSpec``s. The
#: ``zone_spec.RegionSpec`` default is 10 u; the bowl uses a taller box so the
#: zoneline/lava/invisible-wall volumes clear the local relief.
REGION_EXTENT_Z: float = 40.0


# ---------------------------------------------------------------------------
# Collected sidecar metadata (Req 3.7, 10.2 — wiring is wave 5)
# ---------------------------------------------------------------------------
@dataclass
class EdgeMetadata:
    """One realized Edge_Connection, collected for the sidecar (Req 3.7).

    ``side`` / ``edge_type`` mirror the declaration; ``region_id`` is the id of
    the ``RegionSpec`` this edge emitted (``None`` for ``mountain``, which seals
    by slope and emits no region).
    """

    side: str
    edge_type: str
    region_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "side": self.side,
            "edge_type": self.edge_type,
            "region_id": self.region_id,
        }


@dataclass
class BarrierMetadata:
    """A sealing barrier collected for the sidecar (Req 3.7, 10.2).

    ``kind`` is ``"invisible_wall"`` for a ``river``-edge seal (Req 3.5) or
    ``"lava"`` for an interior lava hazard (Req 10.1/10.2). ``damaging`` is
    ``True`` only for lava (Req 10.2); an Invisible_Wall is a pure collision
    barrier, not damaging. ``region_id`` ties it to the emitted ``RegionSpec``.
    """

    kind: str  # "invisible_wall" | "lava"
    region_id: str
    damaging: bool = False
    side: Optional[str] = None  # the Rim side, for an invisible_wall

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind,
            "region_id": self.region_id,
            "damaging": self.damaging,
            "side": self.side,
        }


@dataclass
class BowlResult:
    """The output of :func:`assemble_bowl`.

    ``heights`` is the Rim-sealed / lava-spiked fine heightfield (a COPY of the
    input ``SynthResult.heights`` with the bowl realized on it; Z up).
    ``regions`` is the list of ``RegionSpec``s the bowl emits (Invisible_Wall →
    ``generic``/``APV``, zoneline → ``ATP``, lava → ``ALV``); ``mountain`` emits
    none (sealed by slope). ``edges`` and ``barriers`` are the collected sidecar
    metadata (Req 3.7 / 10.2) — returned here, wired to ``.zone.json`` in wave 5.
    """

    heights: "np.ndarray"
    regions: List[RegionSpec] = field(default_factory=list)
    edges: List[EdgeMetadata] = field(default_factory=list)
    barriers: List[BarrierMetadata] = field(default_factory=list)

    def sidecar_metadata(self) -> Dict[str, object]:
        """The collected region metadata as plain data for the wave-5 sidecar."""
        return {
            "edge_connections": [e.to_dict() for e in self.edges],
            "barriers": [b.to_dict() for b in self.barriers],
        }


# ---------------------------------------------------------------------------
# World-frame helpers (fine grid <-> world XY; Z up)
# ---------------------------------------------------------------------------
def _cell_world_xy(
    i: int, j: int, origin: Tuple[float, float], resolution: float
) -> Tuple[float, float]:
    """World XY of the CENTRE of fine cell ``(i, j)`` (Z up; no height here)."""
    ox, oy = origin
    return ox + (i + 0.5) * resolution, oy + (j + 0.5) * resolution


def _region_from_cells(
    cells: List[Tuple[int, int]],
    heights: "np.ndarray",
    origin: Tuple[float, float],
    resolution: float,
    *,
    region_id: str,
    kind: str,
) -> RegionSpec:
    """Build a ``RegionSpec`` box covering a set of fine cells.

    The box is centred on the cells' XY bounding-box centre at the mean surface
    Z of those cells (Z up), with half-extents spanning the footprint. Used for
    the Invisible_Wall, zoneline and lava volumes.
    """
    xs = [i for (i, _) in cells]
    ys = [j for (_, j) in cells]
    i_lo, i_hi = min(xs), max(xs)
    j_lo, j_hi = min(ys), max(ys)
    x_lo, y_lo = _cell_world_xy(i_lo, j_lo, origin, resolution)
    x_hi, y_hi = _cell_world_xy(i_hi, j_hi, origin, resolution)
    cx = 0.5 * (x_lo + x_hi)
    cy = 0.5 * (y_lo + y_hi)
    zs = [float(heights[i, j]) for (i, j) in cells]
    cz = float(sum(zs) / len(zs)) if zs else 0.0
    ext_x = 0.5 * (x_hi - x_lo) + 0.5 * resolution + REGION_EXTENT_PAD
    ext_y = 0.5 * (y_hi - y_lo) + 0.5 * resolution + REGION_EXTENT_PAD
    return RegionSpec(
        id=region_id,
        kind=kind,
        center_x=cx,
        center_y=cy,
        center_z=cz,
        extent_x=max(ext_x, resolution),
        extent_y=max(ext_y, resolution),
        extent_z=REGION_EXTENT_Z,
    )


def _fine_cells_for_side(
    synth: SynthResult, matrix: DesignMatrix, seg_idx: int
) -> List[Tuple[int, int]]:
    """Fine cells belonging to the Edge_Connection segment ``seg_idx``.

    The synth fine grid tiles each coarse matrix cell into ``factor x factor``
    fine cells (``factor = round(cell_size / resolution)``). A coarse perimeter
    cell whose ``edge_segment`` is ``seg_idx`` contributes its whole fine block.
    """
    factor = max(1, int(round(matrix.cell_size / synth.resolution)))
    out: List[Tuple[int, int]] = []
    nx, ny = matrix.shape
    for ci in range(nx):
        for cj in range(ny):
            cell = matrix.cells[ci, cj]
            if cell.edge_segment != seg_idx:
                continue
            i0, i1 = ci * factor, (ci + 1) * factor
            j0, j1 = cj * factor, (cj + 1) * factor
            for i in range(i0, min(i1, synth.heights.shape[0])):
                for j in range(j0, min(j1, synth.heights.shape[1])):
                    out.append((i, j))
    return out


def _interior_neighbour_mean(
    heights: "np.ndarray", mask: "np.ndarray"
) -> "np.ndarray":
    """Mean height of each masked cell's non-masked 4-neighbours.

    Used to anchor the mountain rim steepening / lava spike against the local
    interior level. NaN where a masked cell has no non-masked neighbour.
    Whole-grid numpy (no per-cell loop).
    """
    acc = np.zeros_like(heights, dtype=np.float32)
    cnt = np.zeros_like(heights, dtype=np.float32)
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb_h = np.roll(heights, shift=(di, dj), axis=(0, 1))
        nb_in = np.roll(~mask, shift=(di, dj), axis=(0, 1))
        acc += np.where(nb_in, nb_h, 0.0)
        cnt += nb_in.astype(np.float32)
    mean = np.where(cnt > 0, acc / np.maximum(cnt, 1.0), np.nan)
    return mean.astype(np.float32)


# ---------------------------------------------------------------------------
# task 9.2 — Rim realization
# ---------------------------------------------------------------------------
def _seal_mountain_by_slope(
    heights: "np.ndarray",
    mountain_mask: "np.ndarray",
    resolution: float,
    agent: AgentModel,
) -> "np.ndarray":
    """Raise ``mountain`` rim cells so their INNER face exceeds the slope cap.

    Req 3.4: the geometry itself seals the edge. The agent stands on a face only
    when its per-cell rise is within ``tan(walkable_slope_deg) * resolution``.
    For each mountain cell we take its local interior-neighbour level and raise
    the cell to at least that level plus ``MOUNTAIN_SEAL_SLOPE_FACTOR`` times the
    walkable per-cell rise — so the step from the adjacent interior up onto the
    rim is well past the cap and the rim faces read non-standable.

    The frozen ridge target (~400 u) already towers over the interior, so this is
    a floor, not a cap: ``np.maximum`` keeps the existing (higher) ridge height
    wherever the freeze already placed it, and only lifts a rim cell that a blend
    left too shallow at the inner transition. No cell is ever lowered. Whole-grid
    numpy. Returns a new array.
    """
    import math

    out = heights.astype(np.float32, copy=True)
    if not mountain_mask.any():
        return out
    walk_rise = math.tan(math.radians(agent.walkable_slope_deg)) * float(resolution)
    min_seal_rise = MOUNTAIN_SEAL_SLOPE_FACTOR * walk_rise
    interior_level = _interior_neighbour_mean(out, mountain_mask)
    # Where a mountain cell borders the interior, require a steep inner step.
    target = interior_level + min_seal_rise
    have = ~np.isnan(target)
    lifted = np.where(mountain_mask & have, np.maximum(out, target), out)
    return lifted.astype(np.float32)


def _realize_rim(
    synth: SynthResult,
    matrix: DesignMatrix,
    heights: "np.ndarray",
    agent: AgentModel,
) -> Tuple[List[RegionSpec], List[EdgeMetadata], List[BarrierMetadata]]:
    """Realize every declared Edge_Connection on ``heights`` (mutated in place).

    Returns the emitted regions and the collected edge / barrier metadata. See
    the module docstring for the per-type behavior (mountain seals by slope;
    river by Invisible_Wall; zoneline as a flat off-map gap).
    """
    regions: List[RegionSpec] = []
    edges: List[EdgeMetadata] = []
    barriers: List[BarrierMetadata] = []

    node_type = synth.node_type
    water_level = float(matrix.water_level)

    # (1) mountain: seal the WHOLE sealed-Rim band by slope in one vectorised
    #     pass (every mountain_rim fine cell), independent of segment — collision
    #     truth is the slope, no region emitted.
    mountain_mask = node_type == "mountain_rim"
    sealed = _seal_mountain_by_slope(heights, mountain_mask, synth.resolution, agent)
    heights[:, :] = sealed

    # (2) per-segment regions for river / zoneline, and the edge-type record.
    for seg_idx, ec in enumerate(matrix.edges):
        side = ec.side
        etype = ec.edge_type
        if etype == "mountain":
            edges.append(EdgeMetadata(side=side, edge_type="mountain", region_id=None))
            continue

        seg_cells = _fine_cells_for_side(synth, matrix, seg_idx)
        if not seg_cells:
            # Degenerate (no fine cells for this segment): still record the type.
            edges.append(EdgeMetadata(side=side, edge_type=etype, region_id=None))
            continue

        if etype == "river":
            # Req 3.5 / 13.1: the boundary water sits at Water_Level (frozen).
            # Water is visual-only, so emit an Invisible_Wall that actually seals
            # the edge — generic -> APV, flagged in the sidecar.
            rid = f"invwall_{side}_{seg_idx}"
            region = _region_from_cells(
                seg_cells, heights, synth.origin, synth.resolution,
                region_id=rid, kind="generic",
            )
            # Anchor the wall volume at Water_Level so it spans the visual edge.
            region.center_z = water_level
            regions.append(region)
            edges.append(EdgeMetadata(side=side, edge_type="river", region_id=rid))
            barriers.append(
                BarrierMetadata(kind="invisible_wall", region_id=rid, damaging=False, side=side)
            )

        elif etype == "zoneline":
            # Req 3.6: flat walkable gap off-map -> RegionSpec(kind="zoneline")
            # (ATP). Held flat by the synth freeze; reachability is proved by the
            # wave-4 built-mesh gate (task 10).
            rid = f"zoneline_{side}_{seg_idx}"
            region = _region_from_cells(
                seg_cells, heights, synth.origin, synth.resolution,
                region_id=rid, kind="zoneline",
            )
            regions.append(region)
            edges.append(EdgeMetadata(side=side, edge_type="zoneline", region_id=rid))

        else:
            # Unknown edge type: record it so nothing is silently dropped. v1
            # never produces this (EDGE_TYPES is {mountain, river, zoneline}).
            edges.append(EdgeMetadata(side=side, edge_type=etype, region_id=None))

    return regions, edges, barriers


# ---------------------------------------------------------------------------
# task 9.3 — interior lava
# ---------------------------------------------------------------------------
def _lava_components(node_type: "np.ndarray") -> List[List[Tuple[int, int]]]:
    """All 4-connected ``lava`` components on the fine grid, as coord lists.

    Lava patches are small interior hazards; each connected patch becomes one
    ``ALV`` region. The scan is over lava cells only (a handful on the fine
    grid), not the whole grid — bounded and cheap.
    """
    nx, ny = node_type.shape
    lava = {
        (i, j)
        for i in range(nx)
        for j in range(ny)
        if node_type[i, j] == "lava"
    }
    comps: List[List[Tuple[int, int]]] = []
    seen: set = set()
    for start in lava:
        if start in seen:
            continue
        comp = [start]
        seen.add(start)
        stack = [start]
        while stack:
            ci, cj = stack.pop()
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (ci + di, cj + dj)
                if nb in lava and nb not in seen:
                    seen.add(nb)
                    comp.append(nb)
                    stack.append(nb)
        comps.append(comp)
    return comps


def _realize_lava(
    synth: SynthResult,
    heights: "np.ndarray",
) -> Tuple[List[RegionSpec], List[BarrierMetadata]]:
    """Realize interior ``lava`` as impassable, damaging terrain (Req 10.1-10.3).

    Each lava cell is spiked ``LAVA_SPIKE_HEIGHT`` above its local
    interior-neighbour level so the per-triangle agent rejects the lava faces as
    non-walkable (steep + beyond ``max_step_up``) — the built-mesh flood cannot
    cross the lava (Req 10.1). Each connected lava patch emits a
    ``RegionSpec(kind="lava")`` (→ ``ALV``) and a barrier record flagged
    **damaging** (Req 10.2). Lava is read from INTERIOR cells only; it is never a
    Rim type (Req 10.3) — this function never touches perimeter edge cells.

    ``heights`` is mutated in place. Returns the emitted ALV regions and the
    collected damaging-barrier metadata.
    """
    regions: List[RegionSpec] = []
    barriers: List[BarrierMetadata] = []

    node_type = synth.node_type
    lava_mask = node_type == "lava"
    if not lava_mask.any():
        return regions, barriers

    # Spike every lava cell above its local interior level so the agent rejects
    # it as floor. Whole-grid numpy: anchor against the non-lava neighbours.
    interior_level = _interior_neighbour_mean(heights, lava_mask)
    have = ~np.isnan(interior_level)
    spike_target = interior_level + LAVA_SPIKE_HEIGHT
    spiked = np.where(lava_mask & have, np.maximum(heights, spike_target), heights)
    heights[:, :] = spiked.astype(np.float32)

    # One ALV region (+ damaging barrier) per connected lava patch.
    for idx, comp in enumerate(_lava_components(node_type)):
        rid = f"lava_{idx}"
        region = _region_from_cells(
            comp, heights, synth.origin, synth.resolution,
            region_id=rid, kind="lava",
        )
        regions.append(region)
        barriers.append(
            BarrierMetadata(kind="lava", region_id=rid, damaging=True, side=None)
        )

    return regions, barriers


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def assemble_bowl(
    synth: SynthResult,
    matrix: DesignMatrix,
    *,
    agent: Optional[AgentModel] = None,
) -> BowlResult:
    """Assemble the bowl from a synthesized heightfield (tasks 9.2 + 9.3).

    Realizes the Rim per each declared ``Edge_Connection`` on a COPY of
    ``synth.heights`` (mountain sealed by slope; river by an Invisible_Wall
    ``RegionSpec``; zoneline as a flat off-map ``zoneline`` region) and turns
    interior ``lava`` into impassable, damaging terrain (an ``ALV`` region plus a
    steep non-walkable spike). Collects the Edge_Connection types and the
    Invisible_Wall / lava barriers as sidecar metadata (Req 3.7 / 10.2 — the
    sidecar is wired in wave 5).

    ``agent`` is the project traversability model whose ``walkable_slope_deg``
    sets the seal slope; the default ``AgentModel`` (40°) matches the gate.

    Returns a :class:`BowlResult`. The input ``synth`` is not mutated.
    """
    if np is None:  # pragma: no cover - numpy is pinned
        raise RuntimeError("numpy is required to assemble a wilderness bowl")

    agent = agent or AgentModel()
    heights = synth.heights.astype(np.float32, copy=True)

    rim_regions, edges, rim_barriers = _realize_rim(synth, matrix, heights, agent)
    lava_regions, lava_barriers = _realize_lava(synth, heights)

    return BowlResult(
        heights=heights,
        regions=rim_regions + lava_regions,
        edges=edges,
        barriers=rim_barriers + lava_barriers,
    )


# ===========================================================================
# task 10.2 — the bowl invariant ON THE BUILT MESH
# ===========================================================================
#
# Tasks 9.2/9.3 (above) REALIZE the bowl on the fine heightfield; task 10.1
# (``analyzer/traverse.py``) added the defaulted bowl-gate PRIMITIVES
# (``OffMapBand`` + ``reached_off_map_segments``, plus the ``build_walk_surface``
# / ``flood_reachable`` the dungeon gate already uses). Task 10.2 — HERE — turns
# a built wilderness TER into a pass/fail VERDICT on the real mesh:
#
#   (1) every ``playable`` cell / POI anchor is reachable from Spawn — one that
#       is NOT is a reachability / walkability failure NAMING the stranded
#       region or anchor (Req 4.2, 4.6, 12.1, 12.2);
#   (2) the Spawn flood must NOT reach any exterior / off-map marker EXCEPT
#       through a ``zoneline`` segment — a ``mountain`` segment stops the flood
#       at the ridge (sealed by slope), a ``river`` segment excludes beyond-edge
#       faces via the Invisible_Wall; a reached non-``zoneline`` band is a
#       BOWL-LEAK failure NAMING the breached Rim segment (Req 4.3, 4.4);
#   (3) every ``zoneline`` segment's gap IS reachable from Spawn AND DOES lead
#       off-map — the intended leak, not a failure (Req 4.5).
#
# The verdict POLICY lives here (the wilderness module), reading the reusable
# ``reached_off_map_segments`` primitive from ``traverse.py`` — keeping the gate
# primitive generic and the bowl semantics in the bowl module, exactly as the
# off-map-band Open Decision (task 10.1) intended.
#
# --- Building the real TER for the gate ------------------------------------
#
# The full wilderness backend -> TER path (matrix carried on the spec, EQG
# written) is wave-5 task 12.5 and is NOT wired yet. So the gate builds the TER
# the MOST DIRECT available way: :func:`build_bowl_ter` triangulates the bowl's
# Rim-sealed / lava-spiked fine heightfield into an in-memory ``TerFile`` with
# the terrain core's own :func:`_heightfield_to_ter`, then the gate runs the
# project traversability agent (``build_walk_surface`` + ``flood_reachable``)
# DIRECTLY on that ``TerFile`` — the identical per-triangle walk surface the
# dungeon/city gate uses on a shipped ``.eqg``, just skipping the PFS packaging
# step wave 5 adds. This is the REAL built mesh (the collision-truth triangles),
# not a matrix-level proxy: the flood climbs (or fails to climb) the exact
# sealed-by-slope ridge and lava spikes the bowl assembly produced.
#
# World frame: :func:`_heightfield_to_ter` places height sample ``(i, j)`` at
# world ``(i * resolution, j * resolution, heights[i, j])`` (origin at 0,0). The
# matrix origin is a pure translation applied identically to the mesh, the Spawn
# point AND the off-map bands, so the seal check (a point-in-rect of reached
# centroids against the bands) is translation-invariant — we therefore compute
# Spawn and the bands in that SAME ``i * resolution`` frame and drop the matrix
# origin offset uniformly. Z is up throughout (EverQuest convention).


@dataclass
class BowlLeak:
    """A breached non-``zoneline`` Rim segment (Req 4.4)."""

    segment_id: str
    side: str
    edge_type: str

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return (
            f"BOWL-LEAK: Rim segment {self.segment_id!r} "
            f"(side {self.side}, {self.edge_type}) is reachable from Spawn — "
            f"the flood escaped the bowl through it"
        )


@dataclass
class ReachabilityFailure:
    """A stranded playable region / anchor (Req 4.6 / 12.2)."""

    region: str
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"UNREACHABLE: playable {self.region} not reachable from Spawn — {self.detail}"


@dataclass
class ZonelineFailure:
    """A ``zoneline`` gap that is not reachable or does not lead off-map (Req 4.5)."""

    segment_id: str
    side: str
    reason: str

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return (
            f"ZONELINE: gap {self.segment_id!r} (side {self.side}) {self.reason} "
            f"— a zoneline must be reachable from Spawn AND lead off-map"
        )


@dataclass
class BowlCheckResult:
    """The verdict of :func:`check_bowl` on the built mesh.

    ``passed`` is True iff the interior is fully reachable (no
    :class:`ReachabilityFailure`), the Rim is sealed (no :class:`BowlLeak`) and
    every ``zoneline`` gap is reachable-and-off-map (no :class:`ZonelineFailure`).
    The failure lists NAME the offending segment / region (Req 4.4 / 4.5 / 4.6 /
    12.2); the diagnostic counts help a 3D-pass reviewer.
    """

    passed: bool
    leaks: List[BowlLeak] = field(default_factory=list)
    unreachable: List[ReachabilityFailure] = field(default_factory=list)
    zoneline_failures: List[ZonelineFailure] = field(default_factory=list)
    # Diagnostics (not pass/fail): the built mesh + flood shape.
    total_faces: int = 0
    standable_faces: int = 0
    reachable_faces: int = 0
    playable_faces: int = 0
    seed_face: Optional[int] = None
    segment_reached: Dict[str, bool] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"[{status}] bowl invariant on the built mesh"]
        lines.append(
            f"  mesh: {self.total_faces} faces  {self.standable_faces} standable  "
            f"{self.reachable_faces} reachable from Spawn (seed_face={self.seed_face})"
        )
        lines.append(
            f"  playable faces: {self.playable_faces}  "
            f"unreachable={len(self.unreachable)}  leaks={len(self.leaks)}  "
            f"zoneline_failures={len(self.zoneline_failures)}"
        )
        for leak in self.leaks:
            lines.append(f"    XX {leak}")
        for ur in self.unreachable:
            lines.append(f"    XX {ur}")
        for zf in self.zoneline_failures:
            lines.append(f"    XX {zf}")
        for n in self.notes:
            lines.append(f"  note: {n}")
        return "\n".join(lines)


def build_bowl_ter(
    bowl: BowlResult,
    synth: SynthResult,
    *,
    name: str = "wild_bowl",
) -> TerFile:
    """Triangulate the bowl's Rim-sealed fine heightfield into a ``TerFile``.

    The most direct available TER path for the bowl gate (the full
    backend->TER wiring is wave-5 task 12.5): height sample ``(i, j)`` becomes a
    vertex at the CELL-CENTRE world XY ``_cell_world_xy(i, j, origin, res)``
    (``origin + ((i+0.5)*res, (j+0.5)*res)``) at height ``heights[i, j]``, with
    gradient normals and two CCW (from +Z) triangles per grid quad — the SAME
    triangulation the terrain core ships. Crucially the vertex frame is the
    EXACT frame the bowl assembly's ``RegionSpec`` footprints and ``_cell_world_xy``
    use, so the mesh, the off-map bands, the Spawn point, the playable mask AND
    the Invisible_Wall rects all live in ONE world frame — no translation to
    reconcile. Z is up.
    """
    if np is None:  # pragma: no cover - numpy is pinned
        raise RuntimeError("numpy is required to build a wilderness bowl TER")

    h = np.asarray(bowl.heights, dtype=np.float32)
    res = float(synth.resolution)
    ox, oy = synth.origin
    nx, ny = h.shape

    ter = TerFile(name=name, magic=MAGIC_TERRAIN, version=2)
    mat = Material(index=0, name="ground", shader="Opaque_MaxCB1.fx")
    mat.add_diffuse("ground.dds")
    ter.materials.append(mat)

    # Gradient normals (central differences), matching _heightfield_to_ter.
    gx, gy = np.gradient(h, res)
    nlen = np.sqrt(gx ** 2 + gy ** 2 + 1.0)
    nx_n = -gx / nlen
    ny_n = -gy / nlen
    nz_n = np.ones_like(h) / nlen

    def vid(i: int, j: int) -> int:
        return i * ny + j

    for i in range(nx):
        for j in range(ny):
            x = ox + (i + 0.5) * res
            y = oy + (j + 0.5) * res
            ter.vertices.append(Vertex(
                x=float(x), y=float(y), z=float(h[i, j]),
                nx=float(nx_n[i, j]), ny=float(ny_n[i, j]), nz=float(nz_n[i, j]),
                u=0.0, v=0.0,
            ))

    for i in range(nx - 1):
        for j in range(ny - 1):
            a = vid(i, j)
            b = vid(i + 1, j)
            c = vid(i + 1, j + 1)
            d = vid(i, j + 1)
            ter.polygons.append(Polygon(a, b, c, material=0, flags=0))
            ter.polygons.append(Polygon(a, c, d, material=0, flags=0))

    return ter


def _segment_band(
    synth: SynthResult, matrix: DesignMatrix, seg_idx: int
) -> Optional[Tuple[float, float, float, float]]:
    """Off-map XY band for Rim segment ``seg_idx`` in the TER's ``i*res`` frame.

    The band is the axis-aligned bounding rect of that segment's fine perimeter
    cells (the Rim ridge / zoneline floor), padded by half a cell so a reached
    face centroid sitting on the outer node row lands inside it. Returns ``None``
    when the segment owns no fine cells (degenerate declaration).

    This is the faithful proxy for "the flood escaped the bowl HERE" (module
    note in ``analyzer/traverse.py``): for a sealed ``mountain`` segment the
    ridge faces are non-standable (steep) so the flood never climbs into the
    band; a breached segment leaks a standable, reachable face into it. For a
    ``zoneline`` segment the flat gap faces ARE standable and the flood is
    REQUIRED to reach the band (Req 4.5).
    """
    cells = _fine_cells_for_side(synth, matrix, seg_idx)
    if not cells:
        return None
    res = float(synth.resolution)
    xy = [_cell_world_xy(i, j, synth.origin, res) for (i, j) in cells]
    xs = [p[0] for p in xy]
    ys = [p[1] for p in xy]
    half = 0.5 * res
    return (min(xs) - half, min(ys) - half, max(xs) + half, max(ys) + half)


def _spawn_world_point(
    synth: SynthResult, matrix: DesignMatrix, heights: "np.ndarray"
) -> Tuple[float, float, float]:
    """Spawn's world XY (TER ``i*res`` frame) + its surface Z from the bowl field.

    The matrix Spawn cell ``(cx, cy)`` maps to the fine-node near the centre of
    its fine block; Z is read from the built heightfield so the flood seeds from
    the floor the player actually stands on (Z is up).
    """
    factor = max(1, int(round(matrix.cell_size / synth.resolution)))
    cx, cy = matrix.spawn
    fi = int(round((cx + 0.5) * factor))
    fj = int(round((cy + 0.5) * factor))
    fi = min(max(fi, 0), heights.shape[0] - 1)
    fj = min(max(fj, 0), heights.shape[1] - 1)
    res = float(synth.resolution)
    x, y = _cell_world_xy(fi, fj, synth.origin, res)
    return (x, y, float(heights[fi, fj]))


def _playable_face_set(
    surf, synth: SynthResult, matrix: DesignMatrix
) -> set:
    """Standable face indices whose centroid lies on a PLAYABLE fine cell.

    Playable = ``synth.playable_interior_mask`` (plains + zoneline_gap ground)
    PLUS the Spawn cell, so Spawn ground always counts (Req 4.1 / 12.3). Scenic
    rim / mountains / water / lava / cliff are excluded — they are deliberately
    unreachable and must NOT be required (Req 4.1). Built in the TER ``i*res``
    frame: a face's centroid XY -> owning fine cell -> is that cell playable?
    """
    if np is None:  # pragma: no cover
        raise RuntimeError("numpy is required for the bowl gate")

    playable_mask = np.asarray(synth.playable_interior_mask, dtype=bool).copy()
    # Ensure the Spawn fine block is playable (Spawn ground is playable by R2.4).
    factor = max(1, int(round(matrix.cell_size / synth.resolution)))
    cx, cy = matrix.spawn
    i0, i1 = cx * factor, (cx + 1) * factor
    j0, j1 = cy * factor, (cy + 1) * factor
    playable_mask[i0:min(i1, playable_mask.shape[0]),
                  j0:min(j1, playable_mask.shape[1])] = True

    res = float(synth.resolution)
    ox, oy = synth.origin
    nx, ny = playable_mask.shape
    std_idx = np.nonzero(surf.standable)[0]
    out: set = set()
    if len(std_idx) == 0:
        return out
    cen = surf.centroids[std_idx]
    # Face centroid XY -> owning fine cell index. A vertex (i,j) sits at
    # origin + (i+0.5)*res; a quad centroid sits ~ a half-cell further, so the
    # owning cell is floor((xy - origin) / res) clamped to the grid.
    gi = np.clip(np.floor((cen[:, 0] - ox) / res).astype(np.int64), 0, nx - 1)
    gj = np.clip(np.floor((cen[:, 1] - oy) / res).astype(np.int64), 0, ny - 1)
    for k in range(len(std_idx)):
        if playable_mask[gi[k], gj[k]]:
            out.add(int(std_idx[k]))
    return out


def _invisible_wall_faces(surf, bowl: BowlResult) -> set:
    """Standable face indices the Invisible_Wall barriers exclude from the flood.

    A ``river`` Edge_Connection seals by an Invisible_Wall ``RegionSpec`` (Req
    3.5), NOT by mesh slope — the boundary water sits flush at ``Water_Level``,
    so the walkable floor would otherwise run right onto it and the flood would
    escape across the visible water edge. The design's seal mechanism is that
    the Invisible_Wall "excludes the beyond-edge faces from adjacency": the gate
    HONORS that here by dropping every standable face whose centroid XY lies
    inside an invisible-wall region's footprint, so the flood stops at the wall
    exactly as a player does. (Water is visual-only — no collision volume — so
    the wall is the only thing that seals a river edge; a gate that ignored it
    would wrongly report a leak the client never has.)
    """
    if np is None:  # pragma: no cover
        raise RuntimeError("numpy is required for the bowl gate")
    rects: List[Tuple[float, float, float, float]] = []
    wall_ids = {b.region_id for b in bowl.barriers if b.kind == "invisible_wall"}
    by_id = {r.id: r for r in bowl.regions}
    for rid in wall_ids:
        r = by_id.get(rid)
        if r is None:
            continue
        rects.append((
            r.center_x - r.extent_x, r.center_y - r.extent_y,
            r.center_x + r.extent_x, r.center_y + r.extent_y,
        ))
    if not rects:
        return set()
    std_idx = np.nonzero(surf.standable)[0]
    if len(std_idx) == 0:
        return set()
    cen = surf.centroids[std_idx]
    walled: set = set()
    for (x0, y0, x1, y1) in rects:
        inside = ((cen[:, 0] >= x0) & (cen[:, 0] <= x1) &
                  (cen[:, 1] >= y0) & (cen[:, 1] <= y1))
        for k in np.nonzero(inside)[0]:
            walled.add(int(std_idx[k]))
    return walled


def _flood_excluding(surf, seed_face: int, exclude: set) -> set:
    """BFS from ``seed_face`` across walkable adjacency, never entering
    ``exclude`` (the Invisible_Wall faces). Mirrors ``flood_reachable`` but
    treats the excluded faces as impassable — the barrier the client has."""
    reached: set = set()
    if seed_face is None or seed_face in exclude or seed_face not in surf.adjacency:
        return reached
    stack = [seed_face]
    reached.add(seed_face)
    while stack:
        f = stack.pop()
        for nb in surf.adjacency.get(f, ()):
            if nb not in reached and nb not in exclude:
                reached.add(nb)
                stack.append(nb)
    return reached


def check_bowl(
    bowl: BowlResult,
    synth: SynthResult,
    matrix: DesignMatrix,
    *,
    agent: Optional[AgentModel] = None,
    ter: Optional[TerFile] = None,
) -> BowlCheckResult:
    """Prove the bowl invariant on the REAL built mesh (task 10.2, Req 4.2-4.6 / 12).

    Builds (or accepts) the bowl's TER, runs the project traversability agent on
    it, floods walkable faces from the Spawn face, and returns a
    :class:`BowlCheckResult`:

    1. **Interior reachable** (Req 4.2 / 4.6 / 12.1 / 12.2): every playable fine
       cell with standable floor must have at least one of its faces in the
       reachable set. A playable cell with floor but no reached face is a
       :class:`ReachabilityFailure` NAMING the stranded cell.
    2. **Rim sealed** (Req 4.3 / 4.4): for every non-``zoneline`` segment, the
       flood must NOT reach the segment's off-map band. A reached band is a
       :class:`BowlLeak` NAMING the breached segment.
    3. **Zonelines lead off-map** (Req 4.5): every ``zoneline`` segment's band
       MUST be reached from Spawn (reachable AND leading off-map). A zoneline
       band the flood never reaches is a :class:`ZonelineFailure`.

    This is ANALYTICAL (the per-triangle agent on the built TER). The VISUAL 3D
    confirmation is the human-gated task 11.2 — nothing here is eyeballed in the
    live viewer.
    """
    if np is None:  # pragma: no cover - numpy is pinned
        raise RuntimeError("numpy is required to check a wilderness bowl")

    agent = agent or AgentModel()
    if ter is None:
        ter = build_bowl_ter(bowl, synth)

    surf = build_walk_surface(ter, agent)
    result = BowlCheckResult(
        passed=False,
        total_faces=len(surf.faces),
        standable_faces=int(surf.standable.sum()),
    )

    # Seed the flood from the Spawn face (the floor under Spawn).
    from analyzer.traverse import _nearest_standable_face  # internal primitive

    spawn_pt = _spawn_world_point(synth, matrix, bowl.heights)
    seed_face = _nearest_standable_face(
        surf, np.asarray(spawn_pt, dtype=np.float64), xy_radius=float(synth.resolution) * 8.0
    )
    result.seed_face = seed_face
    if seed_face is None:
        result.notes.append("no standable face under Spawn — the built mesh has no walkable floor")
        return result

    # Honor the Invisible_Wall barriers (river-edge seal, Req 3.5): the flood
    # cannot cross a wall, exactly as a player cannot. See _invisible_wall_faces.
    walled = _invisible_wall_faces(surf, bowl)
    if walled:
        result.notes.append(f"{len(walled)} face(s) behind Invisible_Wall(s) excluded from the flood")
    reached = _flood_excluding(surf, seed_face, walled)
    result.reachable_faces = len(reached)

    # --- (1) interior reachability among PLAYABLE faces only ---------------
    playable_faces = _playable_face_set(surf, synth, matrix)
    result.playable_faces = len(playable_faces)
    # Group playable faces by owning fine cell so a stranded cell is NAMED.
    res = float(synth.resolution)
    ox, oy = synth.origin
    nx_f, ny_f = synth.heights.shape
    std_cell: Dict[Tuple[int, int], List[int]] = {}
    for f in playable_faces:
        c = surf.centroids[f]
        gi = int(min(max(int((c[0] - ox) // res), 0), nx_f - 1))
        gj = int(min(max(int((c[1] - oy) // res), 0), ny_f - 1))
        std_cell.setdefault((gi, gj), []).append(f)
    for (gi, gj), faces in sorted(std_cell.items()):
        if not any(f in reached for f in faces):
            result.unreachable.append(ReachabilityFailure(
                region=f"playable cell ({gi},{gj})",
                detail=f"{len(faces)} standable floor face(s), none reachable from Spawn",
            ))

    # --- (2)/(3) Rim seal + zoneline via the off-map bands -----------------
    bands: List[OffMapBand] = []
    seg_meta: Dict[str, Tuple[str, str]] = {}  # segment_id -> (side, edge_type)
    for seg_idx, ec in enumerate(matrix.edges):
        band = _segment_band(synth, matrix, seg_idx)
        if band is None:
            continue
        seg_id = f"{ec.side}:{seg_idx}:{ec.edge_type}"
        is_zone = ec.edge_type == "zoneline"
        bands.append(OffMapBand(segment_id=seg_id, band=band, is_zoneline=is_zone))
        seg_meta[seg_id] = (ec.side, ec.edge_type)

    reached_segments = reached_off_map_segments(surf, reached, bands)
    result.segment_reached = dict(reached_segments)
    for seg_id, did_reach in reached_segments.items():
        side, etype = seg_meta[seg_id]
        if etype == "zoneline":
            # The intended leak: MUST be reached (reachable + leads off-map).
            if not did_reach:
                result.zoneline_failures.append(ZonelineFailure(
                    segment_id=seg_id, side=side,
                    reason="is not reachable from Spawn (or does not lead off-map)",
                ))
        else:
            # mountain / river: reaching the exterior band is a bowl leak.
            if did_reach:
                result.leaks.append(BowlLeak(
                    segment_id=seg_id, side=side, edge_type=etype,
                ))

    result.passed = (
        not result.unreachable
        and not result.leaks
        and not result.zoneline_failures
    )
    return result
