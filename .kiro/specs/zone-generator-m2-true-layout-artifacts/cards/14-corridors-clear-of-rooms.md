# 14 — Corridors stay out of rooms; corridor bends have walls

Index entry: `tasks.md` task 14. Found by tasks 4 and 5 (2026-10-31). No
requirement number; it's a layout/geometry defect the traversability gate can't
see.

## Goal
Two defects show up as false floors and ledges in the traced outline:

1. **Corridors run inside rooms.** `_separate_rooms` in `generators/layout.py`
   keeps rooms only `max(corridor_width * 0.5, 30)` apart. A Z-corridor puts its
   full-width middle leg in that gap, so it reaches about 19 u into each room.
   With elevation the middle leg is the ramp, so it runs under one room's floor
   and over the other's. Seed 1955208177: `corr_4` is 77.6 u wide between walls
   38.8 u apart; `corr_0`, `corr_7`, `corr_8`, `corr_9` and seed 678358326 are
   the same. Seed 7 (30 rooms) also has two corridors crossing about 13 u apart.
   `validate(check_corridors=True)` passes all of them.
2. **Corridor bends have holes.** On the flat seed 1516796975 the outline has
   38.8 × 38.8 u L-shaped ledge pieces at corridor bends and 19.4 u pieces beside
   doorways: missing wall at the outer corner of a bend (the doorway pieces may
   be defect 1).

Fix both at the root so no corridor floor lies inside a room footprint except
its doorway end, and every corridor bend is walled.

## Done when
- [ ] Decide between keeping rooms at least a full corridor width apart (moves
      room layouts) and routing the Z middle leg inside the gap (moves corridors
      only); measure both on the three test seeds and record the choice and why
      in the commit body and in `archive.md` "Decisions".
- [ ] No corridor's floor overlaps a room footprint beyond its doorway inset,
      on any layout seed, flat or elevated.
      → verify: a property in new `tests/test_corridor_clearance.py`, 25 layouts, using `routing.route_footprint`.
- [ ] Box builds have no Stacked_Floors: `mapgeom.depth_bands` gives one band on
      seeds 1955208177, 1516796975, 678358326 and 7 (30 rooms), and on 15 random
      elevated builds (`slow`).
      → verify: `python -m pytest tests/test_corridor_clearance.py -q`.
- [ ] Corridor bends are walled: on seed 1516796975, `mapgeom.extract_outline`
      reports no ledge pieces (a flat zone has none where walls are complete).
- [ ] The validator would have caught defect 1: a corridor floor inside a room
      footprint fails `validate(check_corridors=True)`, or say in the commit body
      why it can't and the new property is the guard instead.
- [ ] `python -m pytest tests/ -q` is green with no loosened test.

## Pitfalls
- Read lessons-learned on Z-routes, subdivided ramps, and bounding elevation by
  the corridor run: a longer or shorter middle leg changes the ramp grade.
- Spacing rooms further apart is a layout break for most seeds (like M1
  Decision 13); record it in the commit body.
- Task 2's doorway walls cut openings from `routing.corridor_route`; if routes
  change, they must still line up.
- If the fix needs `analyzer/traverse.py` (not in Owns), stop and say so.
- The agent can't check this in 3D; say so in Result. Task 12 eyeballs it.

## Result
