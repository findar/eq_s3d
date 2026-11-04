# 2 — The gate learns stairs and bridges

Index entry: `tasks.md` task 2. Requirements 2. Design V1.

## Goal
The walk gate understands Staircases (and Bridges) before any layout makes them: `classify_corridor` and the corridor-continuity check judge risers, treads, headroom and landings, and a deck crossing another room's air; failures are named.

## Done when
- [x] Property tests over generated stair corridors (a builder in the test file, using `generators/geometry.py`'s existing `steps > 0` path): risers ≤ step-up, treads ≥ the minimum and headroom ≥ player height pass; a riser too tall, a tread too short, no headroom, a gap at a landing each fail with a reason naming it.
- [x] A bridge case built by hand in the test (a deck through a tall room's volume, flush at both ends) passes; a gap at a bridge end fails.
- [x] Each failure class pinned as a regression example.
      → verify: `python -m pytest tests/test_traverse_connectors.py -q`
- [x] `python -m pytest tests/ -q` is green; no existing gate result changes.

## Pitfalls
- lessons-learned "A ramp must be SUBDIVIDED": faces join only within the step-up in Z; a riser must not leave tread centroids further apart than that.
- The gate's room-face test is XY today; a stacked room's floor would count as the lower room's. That fix is task 5's (it needs Levels); here, test connectors only.

## Result
✔ 8d61e7d · 1252 passed
