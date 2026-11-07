# 14 — Rooms draw their Scales

Index entry: `tasks.md` task 14. Requirements 11.1, 11.2, 11.4.

## Goal
Each room gets finish, structure and clutter, leaning toward its neighbours. Recorded, and acting on nothing yet.

## Done when
- [x] The draw per the design, in graph order, from its own stream (F12): `python -m pytest tests/test_room_scales.py -q`.
- [x] Sidecar `layout.rooms.<id>.scales` holds the values; `python -m pytest tests/test_topology_levels.py -q` is green with no golden moved except by the new key.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Classic, cities and wilderness draw nothing: their goldens must not move.

## Result
✔ f4b34f6 · 1853 passed
