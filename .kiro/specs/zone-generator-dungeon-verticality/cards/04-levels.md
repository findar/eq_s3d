# 4 — Levels and stacking in the graph engine

Index entry: `tasks.md` task 4. Requirements 4.1, 4.2. Design "Levels", "Stacking".

## Goal
The graph engine gives rooms Levels from the rules' relations, the rewrite driver refuses relation-inconsistent graphs, and placement lets rooms on different Levels overlap in plan through `may_overlap_in_plan`.

## Done when
- [x] V3: over grown graphs, every `above` / `below` / `level` edge agrees with the Levels; the driver rejects an application that makes the relations disagree (new invariant), and the checker rejects a rule whose replacement disagrees with itself.
- [x] `may_overlap_in_plan(a, b)` is true only for rooms on different Levels with at least the Slab between them; placement doesn't push such pairs apart and pulls stair edges together in plan.
- [x] With no vertical relations the engine's output is byte-identical to step 6's (graph goldens captured first, in the test file).
      → verify: `python -m pytest tests/test_topology_levels.py tests/test_topology_embed.py tests/test_topology_rewrite.py -q`

## Pitfalls
- Levels are placement input, not a re-tag after layout (lessons-learned; step 6 decision 1).
- The Slab and Level_Height come from finding 7 and the size classes at race scale (step 6 task 20: rooms are placed at race-scaled size).

## Result
✔ f82d81b · 1270 passed
