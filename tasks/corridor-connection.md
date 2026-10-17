# TASK: corridor-connection

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Box-backend geometry correctness (the dungeon "navigable + enclosed"
north-star the content layer sits on top of)
Last touched: created after commit 9a2a9ef; rescoped after seed 1955208177 diagnosis

## Goal

Make corridors between rooms actually **connect and be traversable** in every
case — including when both rooms face each other on parallel walls, and when
there's an elevation change. Done when a 3D walk across several
elevation-heavy seeds shows every corridor meeting both rooms flush (right XY
AND right floor height at each opening) and walkable (no cliff ramps, no
oversized stair steps), with regression tests enforcing it.

## Root cause (diagnosed on seed 1955208177)

TWO distinct, compounding problems — both in the box backend, independent of
the content layer (reproduce on a plain dungeon):

### 1. Same-axis room pairs can't be served by a single-corner L-bend (PRIMARY)

`geometry.add_corridor` builds a 2-segment **L** (one corner). That works when
the two openings are on perpendicular walls (one N/S, one E/W). But when both
rooms face each other on **parallel** walls (both E↔W, or both N↔S — very
common), an L forces ONE leg to run *parallel* to a wall instead of out through
its opening:

- Flat corridors: the parallel leg barely overlaps the opening — looks connected
  but is fragile.
- Elevation corridors: the parallel leg sits at the WRONG floor height at that
  opening (it carries none / the wrong share of the rise), leaving a vertical
  gap — the room looks unreachable.

On seed 1955208177 all four elevation corridors are same-axis:

```
corr_3 room_4[E]->room_5[W] ramp  dz=+30   parallel leg @ room_5, 30u off
corr_4 room_0[S]->room_6[N] stairs dz=-54  parallel leg @ room_6, ~11u off
corr_5 room_1[E]->room_8[W] ramp  dz=-66   (53deg cliff — see #2)
corr_6 room_1[S]->room_2[N] stairs dz=-73  parallel leg @ room_2, ~15u off
```

This ALSO explains the earlier mis-scoped "ramp gap" finding (seeds 1516796975,
678358326): those were same-axis parallel-leg cases, not a ramp-specific Z bug.

**Fix direction:** detect the same-axis case and emit a **3-segment Z-corridor**
— a perpendicular stub straight out of wall A, a middle cross-jog, a
perpendicular stub into wall B. Each end stub stays flat at its own room's
floor; the middle jog carries the entire elevation change. Keep the existing
L-bend for the genuine cross-axis case, and the straight single leg for
collinear openings. Prefer one shared elevation-split helper so ramp and stair
behave identically (they drifted apart once already — commits 03dc912/9f69d1f).

### 2. Elevation magnitude isn't bounded by corridor run length (SECONDARY)

`LayoutGenerator._assign_elevation` picks per-edge rises of ~20-80u without
regard to how long the corridor between the two rooms' walls actually is. When
the walls are close, the result is unwalkable even if it connects:

```
corr_5 RAMP   dz=-66 over ~49u run  = 53deg  (cliff, not walkable)
corr_6 STAIRS dz=-73 over 5 steps   = 14.6u/step (too tall to climb; player ~6u)
corr_4 STAIRS dz=-54 over 5 steps   = 10.8u/step (too tall)
corr_3 RAMP   dz=+30 over ~83u run  = 20deg  (fine)
```

**Fix direction (decision needed):** either cap the elevation rise to what the
run allows at a walkable grade, and/or scale stair step COUNT to the rise so
steps stay ~a player-step tall (and ensure the run is long enough for them).
This is a layout/elevation concern, arguably separable from #1 — but fixing #1
without #2 still leaves connected-but-impassable corridors, so both need doing
for the reported symptom to actually clear.

## Acceptance criteria

- [ ] Same-axis room pairs get a 3-segment Z-corridor; each end stub is
      perpendicular to its wall and flat at that room's floor_z (verified by a
      test that the corridor floor Z at each opening == room floor_z, <2u).
- [ ] Cross-axis (L-bend) and collinear (straight) corridors still connect
      flush — no regression; existing `TestCorridorRouting` stays green.
- [ ] Elevation corridors are walkable: ramp grade below a walkable cap and/or
      stair step height bounded (e.g. <= ~a player step), across several
      elevation-heavy seeds (incl. 1955208177, 1516796975, 678358326).
- [ ] No floating/overhanging geometry at the corners; corner fills at the
      correct shared height.
- [ ] `docs/ACCEPTANCE.md` section B (Navigability: corridors connect cleanly;
      stairs/ramps continuous) human-confirmed in the 3D viewer for the reported
      seeds plus a couple of random elevation-heavy seeds.

## Subtasks

- [ ] Repro/measure script: for a seed, report each corridor's wall-facing axes,
      floor Z at both openings vs room floor_z, and ramp slope / stair step
      height. Pin the worst seeds. (Use a NEAREST-vertex probe, not a wide window
      — the wide window gave a misleading "ramp gap" reading before.)
- [ ] Implement the Z-corridor (3-segment) router for the same-axis case in
      `generators/geometry.py::add_corridor`; share one elevation-split helper
      with the L-bend so ramp/stair stay consistent.
- [ ] Decide + implement the elevation-steepness fix (#2) — confirm approach
      with the user (cap rise vs. scale step count vs. both).
- [ ] Regression tests in `tests/test_generators.py::TestCorridorRouting`:
      Z-corridor meets both openings at the right floor height; walkable-grade /
      step-height bound; sweep the pinned seeds.
- [ ] Full suite green.
- [ ] Human 3D validation pass on the reported + a couple random seeds; log here.
- [ ] Sync ROADMAP "Known issues" and this file.

## Deliverables

- Code: `generators/geometry.py` (router), possibly `generators/layout.py`
  (`_assign_elevation` steepness cap)
- Tests: `tests/test_generators.py::TestCorridorRouting`
- Docs: ROADMAP known-issues; `.kiro/steering/lessons-learned.md` (new gotcha:
  same-axis pairs need a Z-route, not an L); this task file
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- Supersedes the earlier `connecting-ramps` framing, which was mis-scoped from a
  flawed wide-window measurement. The real root cause is same-axis corridor
  ROUTING (affects ramps AND stairs), plus an orthogonal elevation-steepness
  problem.
- Per the standing lesson: passing structural tests are necessary but NOT
  sufficient — every corridor bug so far (481893615, 1516796975, 1955208177)
  passed the suite and was only caught in the 3D viewer. Keep a human eyeball in
  the acceptance bar, and prefer a nearest-vertex probe over a wide window when
  measuring.
- #2 (steepness) needs a user decision on approach before implementing.
- Don't special-case themed vs. plain zones — box-backend bug, theme-independent.
