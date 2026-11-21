# 9 — Framed corridors wind

Index entry: `tasks.md` task 9. Requirement 8, design "First-look fixes".

## Goal
A rough corridor holding a Transition line winds door to door, straight only through its frame.

## Done when
- [ ] Seed 731402518 (Dungeon, Graph, 12 rooms, Cave, Moderate, Winding 1): `corr_11` has a
      `path`, its line stands square on a straight stretch, and the stray and the count of
      framed corridors with a path over cave graph seeds 1000–1039 go in the commit body.
- [ ] Mesh, `corridor_continuity`, decor RoomContexts and map read the same line (a test in
      tests/test_winding_control.py).
- [ ] `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q -n 4` (alone) green, each moved
      golden named in the commit.

## Pitfalls
- lessons-learned "Geometry / fields" (ramp subdivision, flush openings): the seam split must
  land where the line is, on the path.
- Step 25 decision: a path must clear every room and corridor by a half-width (`route_clear`).

## Result
