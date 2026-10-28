"""
generators/wilderness
----------------------
The terrain-first open-world wilderness zone generator (roadmap step 1 —
the sealed, eroded open Karana).

This package holds the wilderness-only pipeline: biome resolution
(prompt → biome), the Design_Matrix IR, graph-replacement, matrix→heightfield
synthesis, bowl assembly and the built-mesh bowl gate. Each stage is a seam
that is testable and replaceable on its own.

Re-exports are added as the package fills in; for now import submodules
directly (e.g. ``from generators.wilderness.biome_resolve import
resolve_wilderness_intent``).
"""
