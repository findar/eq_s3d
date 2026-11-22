# 9 — Framed corridors wind

Index entry: `tasks.md` task 9. Requirement 8, design "First-look fixes".

## Goal
A rough corridor holding a Transition line winds door to door, straight only through its frame.

## Done when
- [x] Seed 731402518 (Dungeon, Graph, 12 rooms, Cave, Moderate, Winding 1): its framed
      corridors (`corr_5`, `corr_11`) are straight since task 8, with no bend left to cut. Over
      cave graph seeds 1000–1039 at Winding 1, framed Z routes get a path 17/19, each line
      square on a straight stretch; counts and stray before/after in the commit body.
- [x] Mesh, `corridor_continuity`, decor RoomContexts and map read the same line (a test in
      tests/test_winding_control.py).
- [x] `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q -n 4` (alone) green, each moved
      golden named in the commit.

## Pitfalls
- lessons-learned "Geometry / fields" (ramp subdivision, flush openings): the seam split must
  land where the line is, on the path.
- Step 25 decision: a path must clear every room and corridor by a half-width (`route_clear`).

## Result
✔ d32e19a · 4097 passed
