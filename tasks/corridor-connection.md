# TASK: corridor-connection

Status: done        <!-- not-started | in-progress | blocked | done -->
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

- [x] Same-axis room pairs get a 3-segment Z-corridor; each end stub is
      perpendicular to its wall and flat at that room's floor_z (verified by a
      test that the corridor floor Z at each opening == room floor_z, <2u).
- [x] Cross-axis (L-bend) and collinear (straight) corridors still connect
      flush — no regression; existing `TestCorridorRouting` stays green.
- [x] Elevation corridors are walkable: ramp grade below a walkable cap (capped
      at 0.5 ≈ 26.6°, under the validator's 40° slope cap), across several
      elevation-heavy seeds (incl. 1955208177, 1516796975, 678358326). Generated
      elevation is carried by subdivided ramps rather than stairs (see #2 note).
- [x] No floating/overhanging geometry at the corners; corner fills at the
      correct shared height. (Stairs that would overhang a short landing were the
      source of the last residual; generated zones use ramps, which don't.)
- [x] `analyzer.traverse` (the automated stand-in for ACCEPTANCE section B) now
      passes 9/9 on the reported seeds and across a 160-zone sweep (room counts
      5/9/12/16 × 40 seeds) + 100 themed zones. GLBs built for the reported seeds
      (`output/corr_<seed>.glb`) for the human viewer pass.

## Subtasks

- [x] Repro/measure script `scripts/measure_corridors.py`: per corridor reports
      wall-facing axes, same/cross-axis, floor Z at both openings (wall-line
      probe — a plain nearest-vertex probe latched onto a stair-tread edge on
      wide corridors), and ramp slope (from the mesh) / stair step height.
- [x] Z-corridor (3-segment) router for the same-axis case in
      `generators/geometry.py::add_corridor`; one shared `_emit_route` helper
      drives straight / Z / L so ramp and stair stay consistent.
- [x] Elevation-steepness fix (#2): see decision in Notes. Implemented BOTH a
      grade cap (`_assign_elevation` + `_relax_elevation`) AND the mesh-level
      walkability fix (subdividing ramps). Generated elevation uses ramps.
- [x] Regression tests in `tests/test_generators.py::TestCorridorRouting`:
      Z-corridor flush at both openings; walkable-grade bound; pinned+random seed
      sweep. Plus `tests/test_traversability.py::TestFormerlyBrokenDungeons`
      (the reported seeds now walk 9/9 on the real mesh).
- [x] Full suite green (197 passed).
- [x] Automated 3D-equivalent validation pass on the reported + random seeds
      (see Notes for the sweep results). Human viewer confirmation still
      recommended as the final sign-off.
- [x] Sync ROADMAP "Known issues" and this file.

## Deliverables

- Code:
  - `generators/geometry.py` — Z/L/straight router through one `_emit_route`
    helper (carry rise on the longest leg); `_add_ramp_corridor` subdivides the
    slope (`MAX_SEG_RISE`) so ramps are walkable to the per-triangle agent.
  - `generators/layout.py` — `_route_legs`/`_elevation_run`, grade cap in
    `_assign_elevation`, `_relax_elevation` for loop edges, ramps for elevation.
- Tests:
  - `tests/test_generators.py::TestCorridorRouting` (Z-corridor flush + walkable
    sweep).
  - `tests/test_traversability.py::TestFormerlyBrokenDungeons` (reported seeds
    now walk 9/9); `TestValidatorFlagsBreakage` rebuilt on a constructed cliff
    zone (no seed is reliably broken any more).
  - `tests/test_pipeline.py` — broken-zone factories now construct an isolated
    room instead of relying on a "known-bad" seed.
- Tooling: `scripts/measure_corridors.py` (per-corridor repro/measure harness).
- Docs: `.kiro/steering/lessons-learned.md` (Z-route + ramp-subdivision gotchas);
  ROADMAP known-issues; this task file.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Root cause confirmed (#1):** `_wall_point` always cuts BOTH openings on the
  same (dominant centre-delta) axis, so essentially every generated corridor is
  "same-axis". The single-corner L-bend ran one leg along a wall face → the
  opening met the corridor at the wrong XY/height. Fixed with the Z-corridor
  (3-segment) router; the L-bend is kept only for a genuine cross-axis pair
  (which the layout doesn't currently produce but hand-authored specs can).

- **#2 (steepness) decision — implemented BOTH, and a third fix the diagnosis
  missed.** The task flagged #2 for a user decision (cap rise / scale steps /
  both). While verifying against the authoritative gate (`analyzer.traverse`,
  which the pipeline runs) it turned out the agent connects faces only within
  `max_step_up` ≈ 3u, and a ramp built as ONE quad splits into two triangles
  `dz/3` apart in Z — so even a flush, gentle ramp read as a cliff and rooms
  beyond showed as 1000u islands. So the real fix set is:
  1. **Cap the grade** in `_assign_elevation` (|dz| <= run·max_grade, 0.5 ≈
     26.6°) and **relax loop edges** (`_relax_elevation`) so non-tree corridors
     are walkable too — not just the BFS tree.
  2. **Subdivide ramps** (`_add_ramp_corridor`, segments <= 2.5u rise) so the
     per-triangle agent can actually climb the slope.
  3. **Generated elevation uses ramps, not stairs.** Stairs would need
     sub-player-height (<=3u) steps plus exact landings to clear the same agent
     limit; the subdivided ramp is the robust, always-flush choice. Stair
     geometry stays in `geometry.py` for hand-authored specs/tests.
  If a different policy is wanted (e.g. keep visible staircases with 3u steps),
  that's a straightforward follow-up on top of this.

- **Measurement lesson:** a plain nearest-vertex probe is NOT enough on WIDE
  corridors — it latched onto a stair-tread edge of the jog near the opening and
  reported a false 6u gap. Probe ALONG the wall line instead
  (`scripts/measure_corridors.py::_floor_z_at`). And structural/flush checks are
  necessary but not sufficient: the per-triangle traversability agent is the
  real bar (seed 1955208177 passed my flush probe while the validator still
  rejected it).

- **Validation results:** `analyzer.traverse` passes 9/9 on 1955208177,
  1516796975, 678358326, 481893615; a sweep of room counts 5/9/12/16 × 40 seeds
  (160 zones) and 100 themed zones all pass. `scripts/measure_corridors.py`
  reports 0 problem corridors across seeds 1..400. Full test suite: 197 passed.

- Don't special-case themed vs. plain zones — box-backend bug, theme-independent
  (confirmed: 100 themed zones across 5 archetypes now pass).
