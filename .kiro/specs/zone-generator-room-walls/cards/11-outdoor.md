# 11 — Outdoor dungeons

Index entry: `tasks.md` task 11. Requirements 10.

## Goal
A themeless outdoor dungeon defaults to `rough`; the Tunnel gets a Throat; the step 5 and 7 guarantees hold.

## Done when
- [x] Tunnel meets its room; every room reachable from the Outdoor_Spawn; Rock_Cover and one Entrance hold.
      → verify: `python -m pytest tests/test_outdoor_walls.py tests/test_outdoor_dungeon_build.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
`extra_doors` carries the Tunnel today: it must reach the Throat logic.

## Result
✔ 246ea5f · 1609 passed
