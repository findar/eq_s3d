# 9 — Corridors match their rooms

Index entry: `tasks.md` task 9. Requirements 8.

## Goal
Flat and ramp legs in `rough` and `hewn` zones: broken walls, a moved ceiling, inside the footprint. Floors, routes, stairs and bridges as built.

## Done when
- [ ] W8 as properties; `corridor_continuity` passes unchanged; closed where a corridor meets a Throat.
      → verify: `python -m pytest tests/test_rough_corridors.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Bend squares and corner walls (`_add_corner_walls`) keep their vertices. Ramp segments stay subdivided (lessons: a ramp must be subdivided).

## Result
