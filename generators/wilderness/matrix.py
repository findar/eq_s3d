"""
generators/wilderness/matrix.py
-------------------------------
The Design_Matrix IR: the governing 2D terrain layout for a wilderness zone.

This is roadmap step 1's central data model. Intent resolves to a matrix of
typed *terrain* cells; graph-replacement refines terrain regions; the Noise_Pass
+ Erosion synthesize a heightfield *subordinate* to this matrix. The matrix
owns LAYOUT — where the river runs, where a cliff is, which perimeter edges are
mountain vs zoneline — not surface detail.

Crucially, the matrix carries ONLY frozen-Z constraints and typed cells —
NEVER a per-cell surface height. Per-cell surface height is the job of the
Noise_Pass / Erosion (wave 3); Z is up (EverQuest convention, Req 14.3). This
keeps the layout inspectable and property-testable BEFORE any geometry exists
(Req 2.5) — the design's guard against "a room graph in a grass skin."

See the design's "Component: the Design_Matrix IR" section for the exact shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:  # numpy is a hard dependency of the terrain path; the matrix is plain data.
    import numpy as np
except Exception:  # pragma: no cover - numpy is pinned in requirements.txt
    np = None  # type: ignore

# ---------------------------------------------------------------------------
# Typed vocabularies (v1 sets)
# ---------------------------------------------------------------------------
# Python's typing.Literal is the design's declared type for these, but the v1
# membership also has to be checkable at runtime (construction post-conditions,
# property tests), so each Literal is mirrored by a frozenset of its members.

try:
    from typing import Literal

    NodeType = Literal[
        "plains", "river", "cliff", "mountain_rim", "lava", "zoneline_gap", "water"
    ]  # Req 2.2 — the v1 Node_Type set
    IntentTag = Literal["playable", "scenic"]  # Req 2.3
    EdgeType = Literal["mountain", "river", "zoneline"]  # Req 3 — v1 connection types
except Exception:  # pragma: no cover - Literal exists on every supported Python
    NodeType = str  # type: ignore
    IntentTag = str  # type: ignore
    EdgeType = str  # type: ignore

#: Runtime-checkable membership for the Literal vocabularies above.
NODE_TYPES: frozenset = frozenset(
    {"plains", "river", "cliff", "mountain_rim", "lava", "zoneline_gap", "water"}
)
INTENT_TAGS: frozenset = frozenset({"playable", "scenic"})
EDGE_TYPES: frozenset = frozenset({"mountain", "river", "zoneline"})


# ---------------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------------
@dataclass
class MatrixCell:
    """One coarse matrix cell.

    Carries exactly one terrain ``node_type`` and exactly one ``intent`` tag
    (Property 1). Frozen cells (river channel, ``zoneline_gap`` floor,
    ``mountain_rim`` ridge target) are masked out of the Noise_Pass (Req 8.2):
    their terrain is set by ``frozen_z``, a single Z CONSTRAINT — not a
    synthesized surface height. ``edge_segment`` identifies which declared
    Edge_Connection a perimeter cell belongs to (``None`` for interior cells).
    """

    node_type: NodeType
    intent: IntentTag
    frozen: bool = False
    frozen_z: Optional[float] = None
    edge_segment: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_type": self.node_type,
            "intent": self.intent,
            "frozen": self.frozen,
            "frozen_z": self.frozen_z,
            "edge_segment": self.edge_segment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MatrixCell":
        return cls(
            node_type=data["node_type"],
            intent=data["intent"],
            frozen=bool(data.get("frozen", False)),
            frozen_z=data.get("frozen_z"),
            edge_segment=data.get("edge_segment"),
        )


# ---------------------------------------------------------------------------
# Rim / Edge_Connection
# ---------------------------------------------------------------------------
@dataclass
class EdgeConnection:
    """One user-declared Rim segment (Req 3.1).

    N segments are supported; the four-side N/E/S/W default (Req 3.2) is simply
    ``N=4`` with one segment per side. An undeclared perimeter edge defaults to
    ``"mountain"`` during construction (Req 3.3) — that default is applied by
    the matrix builder (task 2.3), not stored here.
    """

    side: str  # "N" | "E" | "S" | "W" (or a segment span)
    edge_type: EdgeType  # undeclared perimeter -> "mountain" (Req 3.3)

    def to_dict(self) -> Dict[str, Any]:
        return {"side": self.side, "edge_type": self.edge_type}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EdgeConnection":
        return cls(side=data["side"], edge_type=data["edge_type"])


# ---------------------------------------------------------------------------
# POI anchors
# ---------------------------------------------------------------------------
@dataclass
class POIAnchor:
    """A named point of interest in world XY.

    v1 carries Spawn (``is_spawn=True``) and optional spawn clearings. Z is
    sampled from the built surface downstream — the anchor itself holds only XY,
    never a surface height (Z is up; the matrix never stores per-point height).
    """

    name: str
    x: float
    y: float
    is_spawn: bool = False
    intent: IntentTag = "playable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "is_spawn": self.is_spawn,
            "intent": self.intent,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "POIAnchor":
        return cls(
            name=data["name"],
            x=float(data["x"]),
            y=float(data["y"]),
            is_spawn=bool(data.get("is_spawn", False)),
            intent=data.get("intent", "playable"),
        )


# ---------------------------------------------------------------------------
# The Design_Matrix
# ---------------------------------------------------------------------------
@dataclass
class DesignMatrix:
    """The governing 2D terrain IR.

    ``cells`` is an ``np.ndarray`` of shape ``(nx, ny)`` and ``dtype=object``
    holding :class:`MatrixCell` instances — a cell ``(i, j)`` covers world XY
    ``[origin_x + i*cell_size, origin_x + (i+1)*cell_size) x [origin_y + j*...)``.
    The matrix is the XY authoring face: it carries frozen-Z CONSTRAINTS only
    (on the cells), never a per-cell surface height. ``water_level`` is the
    single Water_Level plane (Req 13); ``spawn`` is the matrix cell holding
    Spawn (the reachability root); ``edges`` is the Rim as N perimeter segments
    (Req 3.1); ``intent_overrides`` maps a cell coordinate to a user-overridden
    Intent_Tag (Req 4.1).
    """

    cells: Any  # np.ndarray (nx, ny) dtype=object -> MatrixCell
    cell_size: float
    origin: Tuple[float, float]
    water_level: float
    biome: str  # v1: "plains"
    edges: List[EdgeConnection] = field(default_factory=list)
    spawn: Tuple[int, int] = (0, 0)
    intent_overrides: Dict[Tuple[int, int], IntentTag] = field(default_factory=dict)

    # -- grid shape helpers -------------------------------------------------
    @property
    def nx(self) -> int:
        """Number of cells along X."""
        return int(self.cells.shape[0])

    @property
    def ny(self) -> int:
        """Number of cells along Y."""
        return int(self.cells.shape[1])

    @property
    def shape(self) -> Tuple[int, int]:
        return (self.nx, self.ny)

    def cell(self, i: int, j: int) -> MatrixCell:
        """The :class:`MatrixCell` at matrix coordinate ``(i, j)``."""
        return self.cells[i, j]

    def cell_world_center(self, i: int, j: int) -> Tuple[float, float]:
        """World XY of the centre of cell ``(i, j)`` (Z is up; no height here)."""
        ox, oy = self.origin
        return (
            ox + (i + 0.5) * self.cell_size,
            oy + (j + 0.5) * self.cell_size,
        )

    # -- serialization to / from plain data (Req 2.5) ----------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain JSON-able data with NO heightfield built.

        The cell grid flattens to a nested list of per-cell dicts. Nothing in
        the output is a surface height: cells carry at most a ``frozen_z``
        CONSTRAINT. This is the inspectable, property-testable form the matrix
        is validated in before any geometry exists (Req 2.5).
        """
        nx, ny = self.shape
        grid = [[self.cells[i, j].to_dict() for j in range(ny)] for i in range(nx)]
        return {
            "shape": [nx, ny],
            "cell_size": self.cell_size,
            "origin": list(self.origin),
            "water_level": self.water_level,
            "biome": self.biome,
            "edges": [e.to_dict() for e in self.edges],
            "spawn": list(self.spawn),
            # JSON has no tuple keys — emit overrides as a list of records.
            "intent_overrides": [
                {"cell": [i, j], "intent": tag}
                for (i, j), tag in self.intent_overrides.items()
            ],
            "cells": grid,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DesignMatrix":
        """Reconstruct a :class:`DesignMatrix` from :meth:`to_dict` output."""
        if np is None:  # pragma: no cover - numpy is pinned
            raise RuntimeError("numpy is required to rebuild a DesignMatrix grid")
        nx, ny = int(data["shape"][0]), int(data["shape"][1])
        grid = np.empty((nx, ny), dtype=object)
        for i in range(nx):
            for j in range(ny):
                grid[i, j] = MatrixCell.from_dict(data["cells"][i][j])
        overrides: Dict[Tuple[int, int], IntentTag] = {}
        for rec in data.get("intent_overrides", []):
            ci, cj = int(rec["cell"][0]), int(rec["cell"][1])
            overrides[(ci, cj)] = rec["intent"]
        return cls(
            cells=grid,
            cell_size=float(data["cell_size"]),
            origin=(float(data["origin"][0]), float(data["origin"][1])),
            water_level=float(data["water_level"]),
            biome=data["biome"],
            edges=[EdgeConnection.from_dict(e) for e in data.get("edges", [])],
            spawn=(int(data["spawn"][0]), int(data["spawn"][1])),
            intent_overrides=overrides,
        )


# ---------------------------------------------------------------------------
# Terrain-first construction (task 2.3)
# ---------------------------------------------------------------------------
#
# ``build_matrix`` realizes the design's terrain-first construction order
# (design: "Terrain-first construction order (R2.4 / R2.6 / R2.7)"). It leads
# with a plains interior, derives terrain regions WITHIN it, then tags the
# perimeter as Rim per each Edge_Connection — the deliberate opposite of the
# rejected rooms-first drape. The result is a plain-data ``DesignMatrix`` that
# is inspectable/property-testable before a single triangle exists (R2.5).
#
# Open Decision — matrix resolution (recorded for task 8.3 re-tuning):
#   A wilderness zone footprint of ~2400 world units square at ``cell_size``
#   150 u/cell gives a 16x16 matrix (16 cells/side). That sits in the design's
#   ~150-250 u/cell, ~12-20 cells/side band (design "Grid resolution and
#   world-frame mapping"). 150 u was chosen as the lower-coarse end: it keeps
#   the matrix cheap to rewrite and property-test while leaving the interior
#   (14x14 = 196 cells after the 1-cell perimeter ring) wide enough to host a
#   generous plains basin plus a river/cliff/lava region without any one region
#   swallowing the interior (Property 2). The TER upsample (wave 3) stays at the
#   terrain core's ~40-50 u/cell, which is WHY the upsample must preserve sharp
#   edges (R9). Re-tuned against the upsample + the 3D pass in task 8.3.

#: Default zone footprint (world units, square) and matrix cell size. A
#: 2400 u zone at 150 u/cell -> 16x16 matrix. See the Open Decision note above.
DEFAULT_ZONE_SIZE: float = 2400.0
DEFAULT_CELL_SIZE: float = 150.0

#: Default visual Water_Level plane Z (R13). Water is visual-only in v1; this is
#: only the plane height the shoreline/river read against, never a per-cell
#: surface height on the matrix.
DEFAULT_WATER_LEVEL: float = 0.0

#: Frozen-Z ridge target for a ``mountain_rim`` cell (a single Z CONSTRAINT, not
#: a synthesized height — the Noise_Pass/Erosion builds the actual ridge surface
#: subordinate to this in wave 3). Chosen well above the interior so the
#: upsampled edge reads as an impassable ridge (R3.4).
MOUNTAIN_RIM_Z: float = 400.0

#: Frozen-Z floor for a ``zoneline_gap`` cell: a flat walkable gap level with the
#: interior ground (R3.6 / R8.4). Zero == the interior plains reference plane.
ZONELINE_GAP_Z: float = 0.0

#: The four default perimeter sides, in declaration order (R3.2).
DEFAULT_SIDES: Tuple[str, str, str, str] = ("N", "E", "S", "W")


def _rng(seed: int):
    """A deterministic numpy ``Generator`` for ``seed`` (same seed -> same
    matrix, Req 16). numpy's PCG64 is reproducible across runs/platforms."""
    if np is None:  # pragma: no cover - numpy is pinned
        raise RuntimeError("numpy is required to build a DesignMatrix")
    return np.random.default_rng(int(seed) & 0xFFFFFFFF)


def _side_for_perimeter_cell(i: int, j: int, nx: int, ny: int) -> Optional[str]:
    """Which side ("N"/"E"/"S"/"W") a perimeter cell belongs to, or ``None`` if
    the cell is interior. Corners are assigned to a side deterministically (the
    larger-extent axis wins; ties go to the vertical side) so every perimeter
    cell has exactly one owning Edge_Connection (Property 4)."""
    on_w = i == 0
    on_e = i == nx - 1
    on_s = j == 0
    on_n = j == ny - 1
    if not (on_w or on_e or on_s or on_n):
        return None
    # Corner: pick the side whose edge the cell is "more" on. Distance to each
    # owning edge is 0 for both at a corner, so fall back to a fixed priority
    # (N, S take the horizontal corners; E, W own only their non-corner spans).
    if on_n:
        return "N"
    if on_s:
        return "S"
    if on_e:
        return "E"
    return "W"


def _resolve_edges(edges: Optional[List[EdgeConnection]]) -> List[EdgeConnection]:
    """Resolve the declared Edge_Connections into a full four-side Rim.

    The data model supports N segments (R3.1); v1's construction realizes the
    four-side N/E/S/W default (R3.2). Any side the caller did NOT declare
    defaults to an impassable ``mountain`` Rim (R3.3). Passing ``None`` or an
    empty list yields the all-``mountain`` default bowl.

    Declared sides win over the default; the returned list has exactly one
    segment per side in ``DEFAULT_SIDES`` order, so ``edge_segment`` indices on
    the cells line up with this list.
    """
    declared: Dict[str, EdgeType] = {}
    for e in edges or []:
        # A declared side overrides the default; last declaration of a side wins.
        declared[e.side] = e.edge_type
    types: Dict[str, EdgeType] = {
        side: declared.get(side, "mountain") for side in DEFAULT_SIDES
    }

    # Keep the river Rim a single contiguous perimeter run so boundary water is
    # always ONE connected region (R2.7 / Property 3). Adjacent river sides join
    # at their shared corner; a single river side is trivially connected. But
    # rivers on OPPOSITE sides (N&S or E&W) with NO river on a perpendicular
    # side cannot be joined along the boundary, and an interior channel joining
    # them would bisect the playable interior and strand a perpendicular
    # zoneline (an unsatisfiable bowl). In that degenerate case demote one of
    # the two opposite rivers to the safe default `mountain` Rim (R3.3), so the
    # bowl stays sealed, water stays one region, and the interior stays
    # reachable. Deterministic: the second side in DEFAULT_SIDES order is demoted.
    def _is_river(side: str) -> bool:
        return types[side] == "river"

    for a, b, perp in (("N", "S", ("E", "W")), ("E", "W", ("N", "S"))):
        if _is_river(a) and _is_river(b) and not any(_is_river(p) for p in perp):
            types[b] = "mountain"  # demote the later side deterministically

    return [EdgeConnection(side=side, edge_type=types[side]) for side in DEFAULT_SIDES]


def _perimeter_cells_for_side(side: str, nx: int, ny: int) -> List[Tuple[int, int]]:
    """Every perimeter cell owned by ``side`` (consistent with
    :func:`_side_for_perimeter_cell`)."""
    cells: List[Tuple[int, int]] = []
    for i in range(nx):
        for j in range(ny):
            if i in (0, nx - 1) or j in (0, ny - 1):
                if _side_for_perimeter_cell(i, j, nx, ny) == side:
                    cells.append((i, j))
    return cells


def _single_water_region(cells: Any, nx: int, ny: int) -> bool:
    """Whether all ``water`` cells form exactly one 4-connected region
    (Property 3). Returns ``True`` when there are no ``water`` cells."""
    coords = [
        (i, j)
        for i in range(nx)
        for j in range(ny)
        if cells[i, j].node_type == "water"
    ]
    if not coords:
        return True
    water = set(coords)
    seen = {coords[0]}
    stack = [coords[0]]
    while stack:
        ci, cj = stack.pop()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (ci + di, cj + dj)
            if nb in water and nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return len(seen) == len(water)


def _water_components(cells: Any, nx: int, ny: int) -> List[List[Tuple[int, int]]]:
    """All 4-connected ``water`` components as lists of coords."""
    water = {
        (i, j)
        for i in range(nx)
        for j in range(ny)
        if cells[i, j].node_type == "water"
    }
    comps: List[List[Tuple[int, int]]] = []
    seen: set = set()
    for start in water:
        if start in seen:
            continue
        comp = [start]
        seen.add(start)
        stack = [start]
        while stack:
            ci, cj = stack.pop()
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (ci + di, cj + dj)
                if nb in water and nb not in seen:
                    seen.add(nb)
                    comp.append(nb)
                    stack.append(nb)
        comps.append(comp)
    return comps


def _playable_reachable_from_spawn(cells: Any, nx: int, ny: int, spawn: Tuple[int, int]) -> set:
    """Cells reachable from Spawn through non-barrier cells. Barriers are the
    scenic blockers (``mountain_rim``/``water``/``lava``/``cliff``); playable
    ``plains``/``zoneline_gap`` are passable. Mirrors the matrix-level
    reachability the task-3 Property-5 test asserts."""
    barrier = {"mountain_rim", "water", "lava", "cliff"}
    seen = {spawn}
    stack = [spawn]
    while stack:
        ci, cj = stack.pop()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = ci + di, cj + dj
            if 0 <= ni < nx and 0 <= nj < ny and (ni, nj) not in seen:
                if cells[ni, nj].node_type not in barrier:
                    seen.add((ni, nj))
                    stack.append((ni, nj))
    return seen


def _ring1_cycle(nx: int, ny: int) -> List[Tuple[int, int]]:
    """The ring of cells one step inside the perimeter (index 1 .. n-2 on each
    side), as a cyclic clockwise walk. This is the corridor water channels hug
    so they connect boundary river edges WITHOUT cutting the central basin —
    the key to holding Property 3 (one water region) and Property 5 (reachable
    interior) at once. Requires ``nx, ny >= 3``."""
    lo_x, hi_x = 1, nx - 2
    lo_y, hi_y = 1, ny - 2
    if hi_x < lo_x or hi_y < lo_y:
        return []
    ring: List[Tuple[int, int]] = []
    for i in range(lo_x, hi_x + 1):
        ring.append((i, hi_y))          # top edge, W->E
    for j in range(hi_y - 1, lo_y - 1, -1):
        ring.append((hi_x, j))          # right edge, N->S
    for i in range(hi_x - 1, lo_x - 1, -1):
        ring.append((i, lo_y))          # bottom edge, E->W
    for j in range(lo_y + 1, hi_y):
        ring.append((lo_x, j))          # left edge, S->N
    return ring


def _unify_water(
    cells: Any,
    nx: int,
    ny: int,
    water_level: float,
) -> None:
    """Make all ``water`` cells one 4-connected region (R2.7, Property 3).

    River edges can sit on non-adjacent perimeter sides, producing disjoint
    boundary water strips. To unify them WITHOUT walling off the interior, this
    connects them by carving water along the ring one cell inside the perimeter
    (:func:`_ring1_cycle`): a boundary-hugging channel that stays against the
    Rim, so the central basin remains an open, Spawn-reachable plain (holding
    Property 5) while all water becomes one region (holding Property 3).

    The shorter arc of the ring between each pair of water-touching segments is
    carved; a ``zoneline_gap`` on the ring is never overwritten (it is a
    declared off-map exit) — if a gap blocks an arc, the other arc is used.
    """
    comps = _water_components(cells, nx, ny)
    if len(comps) <= 1:
        return

    ring = _ring1_cycle(nx, ny)
    if not ring:
        return
    R = len(ring)

    def _ring_neighbour_of_water() -> List[int]:
        """Ring positions adjacent (4-connectivity) to an existing water cell —
        the hook points where boundary water meets the ring."""
        hooks: List[int] = []
        for k, (i, j) in enumerate(ring):
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = i + di, j + dj
                if 0 <= ni < nx and 0 <= nj < ny and cells[ni, nj].node_type == "water":
                    hooks.append(k)
                    break
        return hooks

    def _adjacent_to_zoneline(i: int, j: int) -> bool:
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < nx and 0 <= nj < ny and cells[ni, nj].node_type == "zoneline_gap":
                return True
        return False

    def _carve_ring(k: int) -> bool:
        i, j = ring[k]
        c = cells[i, j]
        if c.node_type == "zoneline_gap":
            return False  # never overwrite a declared exit
        if _adjacent_to_zoneline(i, j):
            return False  # keep the passage from a zoneline gap into the interior
        c.node_type = "water"
        c.intent = "scenic"
        c.frozen = True
        c.frozen_z = water_level
        return True

    hooks = sorted(set(_ring_neighbour_of_water()))
    if len(hooks) < 2:
        return

    def _water_component_of_hook(k: int) -> Optional[int]:
        """Index of the water component the ring cell at ``k`` touches (or
        ``None``). Recomputed against the live cell grid each call."""
        i, j = ring[k]
        for ci, comp in enumerate(comps):
            cset = set(comp)
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (i + di, j + dj) in cset:
                    return ci
        return None

    # Greedy minimal join: walk the ring's gaps between consecutive hooks
    # (shortest first) and carve an arc only when it links two DIFFERENT water
    # components, until all components are one. This connects the strips with
    # the fewest carved cells, keeping the interior plains-led (Property 2)
    # while making water one region (Property 3).

    # Candidate arcs: between each pair of consecutive hooks (cyclically), the
    # run of ring cells strictly between them, with its length.
    arcs: List[Tuple[int, int, int, List[int]]] = []  # (length, hook_a, hook_b, cells)
    for idx in range(len(hooks)):
        a = hooks[idx]
        b = hooks[(idx + 1) % len(hooks)]
        # Carve INCLUSIVE of both hook endpoints: the hook ring cells are the
        # bridges that touch the boundary water, so they must themselves become
        # water for the arc to actually join the two strips.
        if b > a:
            between = list(range(a, b + 1))
        else:  # wrap
            between = list(range(a, R)) + list(range(0, b + 1))
        arcs.append((len(between), a, b, between))
    arcs.sort(key=lambda t: t[0])

    # Union-find over components.
    parent = {ci: ci for ci in range(len(comps))}

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(x: int, y: int) -> None:
        parent[_find(x)] = _find(y)

    remaining = len(comps)
    for _len, a, b, between in arcs:
        if remaining <= 1:
            break
        ca = _water_component_of_hook(a)
        cb = _water_component_of_hook(b)
        if ca is None or cb is None:
            continue
        if _find(ca) == _find(cb):
            continue
        # Carve this arc; if every cell carved (no zoneline block interrupted
        # it), the two components are now joined.
        ok = all(_carve_ring(k) for k in between) if between else True
        if ok:
            _union(ca, cb)
            remaining -= 1

    # NOTE: ``_resolve_edges`` demotes the one degenerate declaration (two
    # opposite river sides with no perpendicular river) to a single-side /
    # adjacent-run river Rim, so the boundary water here is always joinable
    # along the ring — no straggling second component can survive the greedy
    # join. The construction post-condition (``_assert_construction_invariants``)
    # proves water ended up a single region regardless.


def build_matrix(
    intent: Any,
    edges: Optional[List[EdgeConnection]] = None,
    seed: int = 0,
    *,
    zone_size: float = DEFAULT_ZONE_SIZE,
    cell_size: float = DEFAULT_CELL_SIZE,
    water_level: float = DEFAULT_WATER_LEVEL,
    intent_overrides: Optional[Dict[Tuple[int, int], IntentTag]] = None,
) -> DesignMatrix:
    """Construct a plains-Karana :class:`DesignMatrix`, terrain-first.

    ``intent`` is the resolved wilderness intent (a
    ``generators.wilderness.biome_resolve.WildernessIntent``): its ``biome``
    (always ``plains`` in v1) is carried onto the matrix, and any biome-fallback
    substitution it recorded is preserved through construction (Property 17 —
    the substitution lives on the intent object and is asserted there; the
    matrix only needs to not drop the intent's biome). A plain biome string is
    also accepted for convenience.

    ``edges`` is the declared Rim as a list of :class:`EdgeConnection` segments
    (R3.1); undeclared sides default to impassable ``mountain`` (R3.3). ``None``
    or ``[]`` yields the all-``mountain`` default four-side bowl (R3.2).

    ``seed`` makes construction deterministic (same seed -> same matrix, Req
    16). ``intent_overrides`` maps a cell coordinate to a user-overridden
    Intent_Tag (R4.1, Property 6); it is applied LAST, after default tagging.

    The construction follows the design's terrain-first order exactly:

    1. Fill the interior with ``plains`` and place **Spawn** near interior
       center (R2.4).
    2. Derive terrain regions *within* the plains interior — a boundary-adjacent
       ``river``, a ``cliff`` scenic framing band, and an interior ``lava``
       hazard patch — seeded from ``seed`` so the interior leads with plains and
       no region swallows it (R2.4, Property 2).
    3. Tag every perimeter cell as Rim per its Edge_Connection: ``mountain`` ->
       ``mountain_rim`` frozen to a ridge target, ``river`` -> boundary
       ``water`` + sealing edge, ``zoneline`` -> ``zoneline_gap`` held flat
       (R2.6, R3.2, R3.3, Property 4).
    4. Assign a default Intent_Tag to every region — plains interior + Spawn
       ground ``playable``; Rim / distant mountains / deep water ``scenic``
       (R2.3).
    5. Enforce the single-connected-``water``-region invariant as a construction
       post-condition (R2.7, Property 3).

    The matrix carries only typed cells + frozen-Z CONSTRAINTS — never a
    per-cell surface height (Z is up; the Noise_Pass/Erosion builds height in
    wave 3; R2.5, R14.3).
    """
    if np is None:  # pragma: no cover - numpy is pinned
        raise RuntimeError("numpy is required to build a DesignMatrix")

    rng = _rng(seed)

    # Biome: accept either a WildernessIntent (has a ``biome`` attribute) or a
    # bare string. The substitution record stays on the intent object (Property
    # 17); the matrix just must not lose the resolved biome.
    biome = getattr(intent, "biome", intent)
    if not isinstance(biome, str):
        biome = "plains"

    # --- grid shape ------------------------------------------------------
    n = max(3, int(round(zone_size / cell_size)))  # cells per side (>=3 so an
    #                                                 interior ring exists)
    nx = ny = n
    # Centre the zone footprint on the world origin so Spawn lands near (0,0).
    origin = (-0.5 * nx * cell_size, -0.5 * ny * cell_size)

    cells = np.empty((nx, ny), dtype=object)

    # --- step 1: plains interior + Spawn near centre ---------------------
    for i in range(nx):
        for j in range(ny):
            cells[i, j] = MatrixCell(node_type="plains", intent="playable")

    spawn = (nx // 2, ny // 2)

    # Interior cells are everything off the 1-cell perimeter ring.
    interior = [
        (i, j)
        for i in range(1, nx - 1)
        for j in range(1, ny - 1)
    ]

    resolved_edges = _resolve_edges(edges)

    # --- step 3 (perimeter Rim) is applied first so interior-region deriv can
    #     see which sides are river (to keep water one region), but the cell
    #     TYPES are set here; interior region derivation (step 2) runs after on
    #     interior cells only. ---------------------------------------------
    for seg_idx, ec in enumerate(resolved_edges):
        for (i, j) in _perimeter_cells_for_side(ec.side, nx, ny):
            cell = cells[i, j]
            cell.edge_segment = seg_idx
            if ec.edge_type == "mountain":
                cell.node_type = "mountain_rim"
                cell.intent = "scenic"
                cell.frozen = True
                cell.frozen_z = MOUNTAIN_RIM_Z
            elif ec.edge_type == "river":
                # Boundary-hugging visual water edge (R3.5). The Invisible_Wall
                # that actually seals it is a wave-5 sidecar record; on the
                # matrix the edge is a scenic water cell at Water_Level.
                cell.node_type = "water"
                cell.intent = "scenic"
                cell.frozen = True
                cell.frozen_z = water_level
            elif ec.edge_type == "zoneline":
                # Flat walkable gap leading off-map (R3.6). Playable + frozen
                # flat so it reads as the deliberate leak, reachable from Spawn.
                cell.node_type = "zoneline_gap"
                cell.intent = "playable"
                cell.frozen = True
                cell.frozen_z = ZONELINE_GAP_Z

    # --- step 2: derive terrain regions WITHIN the plains interior -------
    # The interior stays plains-LED: each derived region is bounded to a small
    # fraction of the interior so no one region swallows it (Property 2). All
    # placement is seeded from ``seed`` for determinism.

    def _interior_only(coords):
        return [(i, j) for (i, j) in coords if (i, j) in set(interior)]

    # Keep Spawn and its immediate ring clear of hazards/regions so Spawn ground
    # stays playable plains.
    spawn_clear = {
        (spawn[0] + di, spawn[1] + dj)
        for di in (-1, 0, 1)
        for dj in (-1, 0, 1)
    }

    # (a) A cliff scenic framing band: a short run of cells one ring inside a
    #     randomly chosen non-river/non-zoneline interior edge. Scenic framing,
    #     not a wall across the interior.
    if nx >= 5 and ny >= 5:
        cliff_side = DEFAULT_SIDES[int(rng.integers(0, 4))]
        cliff_len = max(1, min(nx, ny) // 3)
        cliff_cells: List[Tuple[int, int]] = []
        if cliff_side == "N":
            row = ny - 2
            start = 1 + int(rng.integers(0, max(1, (nx - 2) - cliff_len)))
            cliff_cells = [(start + k, row) for k in range(cliff_len)]
        elif cliff_side == "S":
            row = 1
            start = 1 + int(rng.integers(0, max(1, (nx - 2) - cliff_len)))
            cliff_cells = [(start + k, row) for k in range(cliff_len)]
        elif cliff_side == "E":
            col = nx - 2
            start = 1 + int(rng.integers(0, max(1, (ny - 2) - cliff_len)))
            cliff_cells = [(col, start + k) for k in range(cliff_len)]
        else:  # W
            col = 1
            start = 1 + int(rng.integers(0, max(1, (ny - 2) - cliff_len)))
            cliff_cells = [(col, start + k) for k in range(cliff_len)]
        for (i, j) in _interior_only(cliff_cells):
            if (i, j) in spawn_clear:
                continue
            cells[i, j].node_type = "cliff"
            cells[i, j].intent = "scenic"

    # (b) A small interior lava hazard patch, offset from Spawn so it never
    #     strands the spawn ground. A compact 1-2 cell patch, not a barrier.
    if len(interior) >= 9:
        # Pick an interior cell away from Spawn and not already special.
        candidates = [
            (i, j)
            for (i, j) in interior
            if (i, j) not in spawn_clear
            and cells[i, j].node_type == "plains"
        ]
        if candidates:
            li, lj = candidates[int(rng.integers(0, len(candidates)))]
            cells[li, lj].node_type = "lava"
            cells[li, lj].intent = "scenic"

    # --- step 5: single-connected-water post-condition (Property 3) ------
    # River edges put water on the perimeter. Distinct river sides (adjacent
    # sides meet only diagonally at a corner; opposite sides not at all) would
    # otherwise split water into multiple 4-connected regions. Unify them into
    # ONE region: keep the component touching the first water cell as the
    # anchor, and link every other water component to it by carving a short,
    # straight interior ``water`` channel (an L of two axis-aligned runs) to the
    # anchor's nearest water cell. This is the minimal connector that satisfies
    # R2.7 for any river-edge declaration; richer interior tributaries are a
    # wave-2/fast-follow concern, not this construction's job.
    _unify_water(cells, nx, ny, water_level)

    # --- step 4 already applied inline (intent set per region). Apply any
    #     user intent overrides LAST (R4.1, Property 6). -------------------
    overrides: Dict[Tuple[int, int], IntentTag] = {}
    if intent_overrides:
        for (i, j), tag in intent_overrides.items():
            if 0 <= i < nx and 0 <= j < ny and tag in INTENT_TAGS:
                cells[i, j].intent = tag
                overrides[(i, j)] = tag

    matrix = DesignMatrix(
        cells=cells,
        cell_size=float(cell_size),
        origin=origin,
        water_level=float(water_level),
        biome=biome,
        edges=resolved_edges,
        spawn=spawn,
        intent_overrides=overrides,
    )

    # --- construction post-conditions ------------------------------------
    # These make the terrain-first invariants true BY CONSTRUCTION (the task 3
    # property tests, authored concurrently, prove them over the input space).
    _assert_construction_invariants(matrix)
    return matrix


def _assert_construction_invariants(matrix: DesignMatrix) -> None:
    """Post-conditions enforced at construction time (defensive; the task-3
    property tests are the real proof over the input space).

    Checks: every cell has a valid Node_Type + Intent_Tag (Property 1); every
    perimeter cell is Rim-typed and carries an ``edge_segment`` (Property 4);
    water is a single region (Property 3). Raises ``ValueError`` on violation so
    a construction bug surfaces loudly rather than producing a silent bad matrix.
    """
    nx, ny = matrix.shape
    rim_types = {"mountain_rim", "water", "zoneline_gap"}
    for i in range(nx):
        for j in range(ny):
            c = matrix.cells[i, j]
            if c.node_type not in NODE_TYPES:
                raise ValueError(f"cell ({i},{j}) has invalid node_type {c.node_type!r}")
            if c.intent not in INTENT_TAGS:
                raise ValueError(f"cell ({i},{j}) has invalid intent {c.intent!r}")
            is_perimeter = i in (0, nx - 1) or j in (0, ny - 1)
            if is_perimeter:
                if c.edge_segment is None:
                    raise ValueError(f"perimeter cell ({i},{j}) has no edge_segment")
                if c.node_type not in rim_types:
                    raise ValueError(
                        f"perimeter cell ({i},{j}) node_type {c.node_type!r} is not a Rim type"
                    )
    if not _single_water_region(matrix.cells, nx, ny):
        raise ValueError("water cells do not form a single connected region")
