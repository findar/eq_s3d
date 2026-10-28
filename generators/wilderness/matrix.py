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
