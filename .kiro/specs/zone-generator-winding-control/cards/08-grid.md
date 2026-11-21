# 8 — Break the Graph grid

Index entry: `tasks.md` task 8. Requirement 7, design "First-look fixes".

## Goal
A Graph layout's rooms stop lining up in rows and columns, and every edge keeps its wall side.

## Done when
- [ ] A grid score (share of room-centre pairs whose x or y agree within 10 u) on seed 731402518
      (Dungeon, Graph, 12 rooms, Cave, Moderate) and over cave graph seeds 1000–1039 (8–30 rooms),
      before and after, in the commit body. Seed 731402518 visibly off the lattice in `mapview`.
- [ ] `python -m pytest tests/test_topology_embed.py tests/test_graph_layout_plan.py -q` green;
      every edge's `_side_toward` unchanged by the offset (a test).
- [ ] `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q -n 4` (alone) green, each moved
      golden named in the commit.

## Pitfalls
- One opening per wall side (`start_once` docstring, step 6 finding 1): the offset must never flip
  an edge's side. Seed the offset per edge; `embed` must not draw from the shared rng.
- Gate regressions surface in task 10; stop and report a new one rather than loosening a test.

## Result
