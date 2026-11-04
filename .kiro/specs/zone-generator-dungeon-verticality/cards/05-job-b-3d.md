# 5 — The shared layout steps in 3D

Index entry: `tasks.md` task 5. Requirements 4.3–4.5. Design "Stacking", "Staircases".

## Goal
Job B judges rooms and corridors in 3D: separation, crossing splits and conflict drops go through `may_overlap_in_plan` and the Slab; floors sit at Level × Level_Height; an edge across Levels becomes a stair corridor (`steps > 0`, switchback when needed); the gate's room-face test picks a room's own floor.

## Done when
- [ ] V4: no room pair overlaps in plan unless on different Levels with the Slab; no corridor passes through a room without the Slab's clearance.
- [ ] V5: every edge across Levels is a stair corridor; the built graph is connected; the gate finds every room on stacked builds (`_faces_in_room` z-bounded).
- [ ] V6: classic builds byte-identical (step 6's `tests/test_layout_engine.py` goldens); graph builds with no vertical relations byte-identical to step 6.
      → verify: `python -m pytest tests/test_layout_levels.py tests/test_layout_engine.py tests/test_topology_embed.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- lessons-learned "Bound elevation by the corridor run, and clamp loop edges too": stairs carry far more rise per run than ramps; `_relax_elevation` must treat a stair edge's band by its stair grade, not 0.5.
- `CorridorSpec` gains a kind (ramp / stair / bridge) or keeps using `steps`: pick one and keep the old JSON unchanged for corridors without it.

## Result
