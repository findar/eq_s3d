# 11 — Room sizes vary

Index entry: `tasks.md` task 11. Requirement 8, design "First-look fixes".

## Goal
Every zone's rooms take sizes and shapes in stock's proportions per kind of zone.

## Done when
- [x] Task 9's size measures over seeds 2000–2039 for cave, fortress, temple, warren, outdoor
      dungeon, classic fortress and city meet task 9's stock targets; before/after in the commit.
- [x] The Size control still shifts sizes; race bands hold; `tests/test_topology_levels.py` and
      the shape bands green.
- [x] `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q -n 4` (full, alone) green, each
      moved golden named.

## Pitfalls
- Huge rooms push neighbours apart: check door-to-door and draw time (task 8's 30-room seeds).

## Result
✔ 36a6e24, 83686c7 · 4097 passed (the 6 gate builds go to task 12, as the lead set)
