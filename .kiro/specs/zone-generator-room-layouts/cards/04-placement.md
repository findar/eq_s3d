# 4 — Placement and the Spine

Index entry: `tasks.md` task 4. Requirements 4.

## Goal
The Spine, the arrangements (`ring`, `rows`, `corners`, `along_wall`, `far_end`, `centre`, `scatter`, `on_dais`), and dropping what doesn't fit. Pure functions over a room and its doors; no recipes or wiring yet.

## Done when
- [x] F4 as properties over rooms, doors, slots and all three styles' shapes.
- [x] F5: placement draws from its own stream, and each arrangement looks like itself (a ring is a ring).
      → verify: `python -m pytest tests/test_room_placement.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Draw samples and look at them, as step 8 task 3 did: its first shapes passed every test and looked wrong. Rooms come in Outline and plain Box forms.

## Result
✔ 47005fc · 1687 passed
