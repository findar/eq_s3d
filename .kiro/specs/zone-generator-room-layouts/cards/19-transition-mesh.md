# 19 — Transition pieces

Index entry: `tasks.md` task 19. Requirements 14.2, 14.6.

## Goal
Seam, Frame and Breach in the mesh, given by hand in a spec.

## Done when
- [x] A Seam splits a level leg, each part with its look and break, and the sections meet; a Frame is closed solids in the finer style; a Breach's jambs are uneven and its floor flush. All pass the gate: `python -m pytest tests/test_transition_mesh.py -q`.
- [x] A stair or bridge takes its Transition at a door.
- [x] A build with none is byte-identical to before this task.

## Pitfalls
Corridors keep one rise leg (`_emit_route`). Many legs are short: a Seam that can't find room falls back to the door.

## Result
✔ 01d2230 · 1926 passed
