# 3 — Outline extractor and depth bands on synthetic worlds

Index entry: `tasks.md` task 3. Design: "Outline extractor", "Depth bands",
Algorithms `extract_outline` / `depth_bands`, research findings 4 and 6.
Requirements 1, 2.

## Goal
Add `generators/mapgeom.py`: trace the walls and ledges of the walkable floor
from a TER mesh and the safe point, and split stacked floors into at most 4
depth bands. Prove it on small synthetic worlds where the true answer is known.
Task 4 runs it on real builds.

## Done when
- [x] `floor_faces`, `extract_outline`, `depth_bands` and `outline_summary`
      exist as the design specifies; an empty floor region raises
      `EmptyFloorRegion`.
- [x] `analyzer/traverse.py` gains only `seed_face_for(surf, safe_point)`, a
      public wrapper of `_nearest_standable_face`. Nothing else there changes.
- [x] `tests/strategies.py` gains `slab_worlds()` and `stacked_worlds(levels)`;
      `tests/pbt_helpers.py` gains `floor_boundary_samples` and
      `reference_bands`.
- [x] Properties 2–7 hold on synthetic worlds (≥ 100 examples each):
      fidelity, completeness, wall/ledge classification, reachable-only,
      canonical order, depth bands.
      → verify: `python -m pytest tests/test_properties_mapgeom.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Coverage is exact interval arithmetic (design Decision 2). A sampled or
  rastered fallback breaks the 0.05 u bound. Don't add one.
- Floor faces use the SIGNED normal (Decision 1); the validator's `|n_z|` counts
  box ceilings as standable.
- No per-face Python loop over whole terrain meshes: cancel welded interior
  edges vectorised first, so only the perimeter reaches the geometric test
  (lessons-learned: "Never reintroduce a per-voxel Python loop").

## Result
✔ 22c8462 · 517 passed
