# 2 — The gate learns Outlines

Index entry: `tasks.md` task 2. Requirements 3.

## Goal
Before any generator makes one, the gate judges hand-built shaped rooms: every door's Throat walkable from the Core, no wall across a Throat, the surface closed apart from doors and slots. `RoomSpec.outline` exists, `None` by default and left out of JSON when unset.

## Done when
- [x] W4: hand-built meshes with a door with no Throat, a wall across a Throat, and an open seam each fail, named in the diagnosis, pinned as examples.
      → verify: `python -m pytest tests/test_gate_outlines.py -q`
- [x] W3's start: with no Outline every golden is unchanged.
      → verify: `python -m pytest tests/test_layout_engine.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Step 7's `_faces_in_room` tests the Box; a walkable face in a Box corner outside the Outline must not pass for the room. Corridor checks stay on the Box.

## Result
✔ bf75d2e · 1443 passed
