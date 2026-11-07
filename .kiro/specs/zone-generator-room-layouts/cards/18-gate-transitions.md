# 18 — The gate learns Transitions

Index entry: `tasks.md` task 18. Requirements 14.3.

## Goal
The gate catches a bad Transition before any generator makes one.

## Done when
- [x] `check_transitions` fails a step, a narrow frame, low head and an open seam, each named and pinned (F14): `python -m pytest tests/test_gate_transitions.py -q`.
- [x] It reads the mesh at each recorded place, so the generator can't simply trust itself.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Same order as task 2: the check lands first, so it's built on hand-made meshes.

## Result
✔ 6ab56d2 · 1926 passed
