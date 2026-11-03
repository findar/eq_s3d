# 19 — Rooms carry their kind; the rules' deep end is the climax

Index entry: `tasks.md` task 19. Requirements 6.3, 7.4. Added after task 9 (found by it).

## Goal
Two fixes task 9 found. (1) `GraphEngine.generate` puts each room's kind on its `RoomSpec`, so every caller (the outdoor dungeon, tests, scripts) gets the kind → room type map and the size-class area rule; `ai/expand.py`'s `KindedGraphEngine` workaround goes. (2) On grown layouts the rules' `deep` room is the climax: the engine names it, the way it names the entrance (`EngineResult.climax`, passed to `_apply_pacing` like `entry`). Task 9 measured the deepest-by-hops room missing the `deep` room in 52 of 96 graph builds, so the boss sat in `deep` while the `climax` role (and its lighting and size cues) landed on a side room.

## Done when
- [x] `LayoutGenerator(engine="graph")` rooms carry `kind`; `KindedGraphEngine` is removed and `plan_to_spec` output is unchanged by the removal.
- [x] On graph builds the `climax` role and `boss` are the `deep` room, every seed; classic pacing is unchanged (task 2 goldens pass).
- [x] Umbrella Req 21 still holds: one entrance, one climax, solvable gates.
      → verify: `python -m pytest tests/test_graph_layout_plan.py tests/test_topology_embed.py tests/test_layout_engine.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Roles are still derived, not re-tagged after layout: the engine's climax goes in through `_apply_pacing`, as the entry does (umbrella Req 32.2 is amended for the graph engine at the close, decision 26).
- Gating places keys by graph depth from the entrance; it doesn't read the climax, so locks are unaffected. Check.

## Result
✔ a1a472c · 1160 passed
