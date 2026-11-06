# 2 — The gate learns Features

Index entry: `tasks.md` task 2. Requirements 2.

## Goal
Before any generator places one, the gate judges hand-built rooms holding Features: none in a Throat, door pairs joined at clear width with footprints grown, no floor walled off, POIs reachable, a Dais walkable onto. `RoomSpec.features` exists, empty by default and left out of JSON.

## Done when
- [ ] F1: a hand-built case of each failure fails, named, pinned as an example.
      → verify: `python -m pytest tests/test_gate_features.py -q`
- [ ] Every golden is unchanged with no Features.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_topology_levels.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
The walk surface can't see a solid on an unbroken floor (design finding 2): judge from the mesh's wall faces, not `RoomSpec.features`, so the gate doesn't trust the generator. Watch the cost: step 8's gate work took builds from 1 s to 18 s before it was fixed.

## Result
