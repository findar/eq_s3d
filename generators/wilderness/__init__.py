"""
generators/wilderness
----------------------
The terrain-first open-world wilderness zone generator (roadmap step 1 —
the sealed, eroded open Karana).

This package holds the wilderness-only pipeline: biome resolution
(prompt → biome), the Design_Matrix IR, graph-replacement, matrix→heightfield
synthesis, bowl assembly and the built-mesh bowl gate. Each stage is a seam
that is testable and replaceable on its own.

Public surface (re-exported here so tests and downstream code import from
``generators.wilderness`` directly, not the submodules):

- Biome resolution (``biome_resolve``): the ``WildernessIntent`` carried from
  prompt to matrix, its ``BiomeSubstitution`` record, the v1 biome vocabulary
  and the resolver entry points.
- The Design_Matrix IR (``matrix``): the typed vocabularies (``NodeType`` /
  ``IntentTag`` / ``EdgeType`` and their runtime membership frozensets) and the
  data models (``MatrixCell`` / ``EdgeConnection`` / ``POIAnchor`` /
  ``DesignMatrix``).
- ``build_matrix`` — the terrain-first constructor (task 2.3). It is a sibling
  task landing in this same worktree; until it is importable this package still
  imports cleanly (the name is simply absent from ``__all__`` and re-export).
"""

from __future__ import annotations

# --- Biome resolution (task 2.1) ------------------------------------------
from generators.wilderness.biome_resolve import (
    DEFAULT_BIOME,
    V1_BIOMES,
    BiomeSubstitution,
    WildernessIntent,
    resolve_biome,
    resolve_wilderness_intent,
)

# --- Design_Matrix IR (task 2.2) ------------------------------------------
from generators.wilderness.matrix import (
    EDGE_TYPES,
    INTENT_TAGS,
    NODE_TYPES,
    DesignMatrix,
    EdgeConnection,
    EdgeType,
    IntentTag,
    MatrixCell,
    NodeType,
    POIAnchor,
)

__all__ = [
    # biome resolution
    "DEFAULT_BIOME",
    "V1_BIOMES",
    "BiomeSubstitution",
    "WildernessIntent",
    "resolve_biome",
    "resolve_wilderness_intent",
    # matrix IR vocabularies
    "NodeType",
    "IntentTag",
    "EdgeType",
    "NODE_TYPES",
    "INTENT_TAGS",
    "EDGE_TYPES",
    # matrix IR data models
    "MatrixCell",
    "EdgeConnection",
    "POIAnchor",
    "DesignMatrix",
]

# --- Graph_Replacement rewrite layer (wave 2, tasks 5.2-5.4) ---------------
from generators.wilderness.rewrite import (
    Region,
    RegionEdge,
    RegionGraph,
    RewriteError,
    RewriteResult,
    build_region_graph,
    invariants_hold,
    rewrite_matrix,
    rim_is_sealed,
    stranded_playable_cells,
)

__all__ += [
    "Region",
    "RegionEdge",
    "RegionGraph",
    "RewriteError",
    "RewriteResult",
    "build_region_graph",
    "rewrite_matrix",
    "stranded_playable_cells",
    "rim_is_sealed",
    "invariants_hold",
]

# --- Terrain-first constructor (task 2.3, same worktree) -------------------
# build_matrix is added by task 2.3 (it owns matrix.py). Re-export it when it is
# present so ``from generators.wilderness import build_matrix`` works once 2.3
# lands, but keep the package importable before then — this scaffolding task
# (3.1) must not be blocked on a sibling task's merge.
try:  # pragma: no cover - trivially covered once 2.3 lands
    from generators.wilderness.matrix import build_matrix  # type: ignore
except ImportError:  # build_matrix not yet defined on matrix.py
    build_matrix = None  # type: ignore
else:
    __all__.append("build_matrix")
