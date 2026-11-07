# 6 — Rooms get Features in graph builds

Index entry: `tasks.md` task 6. Requirements 4.4, 6, 7.

## Goal
Graph dungeons and outdoor dungeons get Features and POIs, last, after walls. Stacking and bridges respected. Classic, cities and wilderness untouched.

## Done when
- [x] F5, F7 and F8 on built zones; Classic, city and wilderness goldens unchanged; graph goldens recaptured with old and new hashes and the reason.
      → verify: `python -m pytest tests/test_features_build.py tests/test_layout_engine.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Rooms keep their Box for every check outside them. Spawn stands on a Core kept clear.

## Result
✔ 6fc6d69 · 1745 passed
