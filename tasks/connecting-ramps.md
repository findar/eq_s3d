# TASK: connecting-ramps

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Box-backend geometry correctness (serves the dungeon "navigable + enclosed"
north-star that the content layer sits on top of)
Last touched: created after commit 9a2a9ef

## Goal

Make **ramp corridors** (the smooth-slope, `steps=0` path) connect cleanly to
both rooms they join, the way the stepped-staircase path now does. On an L-bend
ramp the corridor floor must meet each room's floor height exactly at that
room's wall opening — no vertical gap, no slope that starts/ends at the wrong
height, no ramp that bleeds across the corner at an interpolated height. Done
when a 3D walk across several elevation-changing seeds shows every ramp meeting
both rooms flush, and a regression test enforces it.

## Background — what's already fixed vs. what remains

Two corridor bugs were fixed recently, both on the **stepped** path / the
routing axis:

- `03dc912` — L-bend staircase resolves the ENTIRE rise on one leg so it lands
  flush at both landings (no interpolated `corner_z`).
- `9f69d1f` — the first leg exits each wall PERPENDICULAR (axis chosen from room
  centres, matching `_wall_point`), fixing disconnected corridors.

The **ramp** path (`_add_ramp_corridor`, `steps=0` with `from_z != to_z`) still
shows gaps. A sweep of L-bend ramp corridors found several where the corridor
floor at a room opening sits tens of units off the room's floor_z, e.g.:

```
seed 1516796975 corr_2  dz=-44.8  from-opening gap=44.8
seed 678358326  corr_2  dz=-60.7  from-opening gap=60.7
seed 13         corr_8  dz=-45.8  from-opening gap=45.8
seed 55         corr_1  dz=+36.2  to-opening   gap=36.2
```

(Repro sweep is in the session log; re-derive with a short script that builds
each corridor mesh and compares floor-vertex Z at each `_wall_point` opening to
the room's `floor_z`.) The root cause is almost certainly the same family as the
stepped fix: on an L-bend the elevation change must resolve on the leg that owns
it and the other leg must stay flat at the room floor it meets — but the ramp
branch and/or the corner-fill height isn't honouring that, so the slope reaches
the opening at the wrong Z.

## Acceptance criteria

- [ ] For every L-bend **ramp** corridor, the corridor floor Z at each room's
      wall opening equals that room's `floor_z` (within a small tolerance, e.g.
      <2u) — verified by a test sweeping several elevation-heavy seeds.
- [ ] Straight (collinear) ramps still meet both openings flush (no regression).
- [ ] The stepped-staircase fixes (`03dc912`, `9f69d1f`) still hold — their
      regression tests stay green.
- [ ] No new floating/overhanging corridor geometry at the corner (the corner
      fill sits at the correct shared height).
- [ ] `docs/ACCEPTANCE.md` section B (Navigability — "corridors connect cleanly",
      "stairs/ramps continuous") human-confirmed in the 3D viewer for the
      reported seeds (1516796975 at minimum) plus a couple of random
      elevation-heavy seeds.

## Subtasks

- [ ] Reproduce + quantify: a small script that, for a given seed, reports each
      ramp corridor's floor Z at both openings vs. the room `floor_z`, so the
      gap is measured not eyeballed. Pin the worst seeds.
- [ ] Diagnose in `generators/geometry.py::add_corridor` /
      `_add_ramp_corridor` / `_add_corner_fill`: confirm whether the ramp leg
      resolves the full `from_z→to_z` and the flat leg + corner sit at the
      matching room floor (the stepped branch already does this; make the ramp
      branch consistent).
- [ ] Fix so the elevation resolves on the correct single leg and the corner
      fill + flat leg land at the room floor. Prefer fixing the shared L-bend
      split so ramp and step behave identically (don't special-case).
- [ ] Add a regression test in `tests/test_generators.py::TestCorridorRouting`
      (e.g. `test_lbend_ramp_meets_both_room_floors`) sweeping the pinned seeds.
- [ ] Run the full suite; keep it green.
- [ ] Human 3D validation pass on the reported + a couple random seeds; log
      findings here.
- [ ] Sync ROADMAP "Known issues" (remove/annotate once fixed) and this file.

## Deliverables

What actually shipped. Fill in as work lands.

- Code: `generators/geometry.py`
- Tests: `tests/test_generators.py::TestCorridorRouting`
- Docs: ROADMAP known-issues + `.kiro/steering/lessons-learned.md` if a new
  gotcha surfaces; this task file kept current
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- This is the ramp counterpart to the two stepped-corridor fixes; the cleanest
  outcome is a SINGLE L-bend elevation-split that both ramp and step share, so
  they can't drift apart again (they already drifted once — the stepped path got
  fixed while the ramp path didn't).
- Per the standing lesson: passing structural tests are necessary but NOT
  sufficient here — all three prior corridor bugs passed the suite and were only
  caught in the 3D viewer. Keep a human eyeball in the acceptance bar.
- Don't special-case themed vs. plain zones — this is a box-backend bug
  independent of the content layer (reproduces on a plain dungeon).
