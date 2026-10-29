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

from analyzer.traverse import AgentModel
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
