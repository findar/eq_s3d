# Archive — test-speed

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | `gate` marker, `quick` profile, 64 tests newly `slow`; quick tier 208 s | `afee5c4`, `01a81e3` |
| 2 | sweep builds pass the plan's verticality; long sweeps split per case; literal examples scale; full 1765 -> 1670 s | `d71a268`, `5cc427f`, `2cffc7d`, `25f29b8` |
| 3 | pytest-testmon measured, not adopted | `ab64237` |
| 4 | `project.md` names the tiers; two lessons | `1821513`, `798b49e` |
| 6 | the traversal gate 2.8x faster, reports identical; full 1323 s, gate tier 768 s | `6e10e38`, `d67c030`, `18bf5a4` |

## Decisions

1. **Step 28 is test speed** (the user, 2026-11-24: "How can we optimize the tests so they
   don't take so long ? That should be a priority to speed up iteration"). Baseline: 3308 s
   wall at `-n 4` alone, 4113 collected. Top files by time among the 150 slowest tests:
   test_vertical_build 2459 s, test_walls_mixed 408, test_topology_levels 340,
   test_properties_pipeline 268, test_site_bands 261, test_bridges 233,
   test_corridor_clearance 207, test_properties_mapgeom 176, test_properties_layout 171.

2. **`-n auto` stays; task 2's bar is 1200 s** (the lead, 2026-11-25, at task 1). Quick tier
   208 s at auto (6.7 GB peak), 246 s at 6, 306 s at 4; full suite 1766 s at auto (13 GB peak),
   so the old 2000 s bar was met by worker count alone.

3. **Task 2's bar is amended to what it measured; the gate's speed is task 6** (the lead,
   2026-11-25). Full suite 1765 -> 1670 s at `-n auto` (worker time 20,256 -> 18,925 s). Repeated
   builds were about 2% of the run, so sharing cannot reach 1200 s; the gate is about 50% of a
   sweep build and also slows every generate. Sweep builds now pass the plan's verticality to
   `generate_validated` (flat plans had failed all 32 quality Draws against moderate's bands).
   Long single sweeps are split per case (collected 4114 -> 4243). Literal `max_examples`
   scale with the profile, except `test_w1_outline...` (see Follow-ups). Coverage cuts were not
   taken.

4. **The gate is 2.8x faster with identical reports; 1323 s accepted** (the lead, 2026-11-25, at
   task 6). Full suite 1670 -> 1323 s, gate tier 1040 -> 768 s, quick 205 s. 144 reports (72
   builds and 72 with 3% of polygons dropped) equal field for field against master's gate. The
   gate is now 10-17% of a sweep build; the rest is decor, map outline and room outlines.

5. **pytest-testmon is not adopted** (the lead, 2026-11-25, at task 3). Quick-tier reruns took
   88-133 s after an edit (205 s plain), 44 s with nothing changed; the full suite saved 17% on
   a traverse edit. It never reruns a test when only a data file changes (golden, room corpus,
   `styles/*.json`), its selection drifts with Hypothesis draws, and plain `--testmon` silently
   runs everything under `-m`. Not worth a dependency that can skip tests unseen.

## Follow-ups
- **Build time outside the gate** (task 6): decor placement, map outline and `generators/outline.py`
  containment now dominate a sweep build; speeding them helps tests and generates alike.
- **`test_corridor_clearance::test_no_corridor_clips_a_room_over_the_sweep`** is one 271 s call;
  split it per case like task 2's splits.
- **Outline fault at thorough** (task 2): `test_outline::test_w1_outline_is_inside_connected_and_reaches_every_door`
  fails in `draw_outline` at 300 examples (Voronoi blob, w=70, fill 0.75, N 0.846, W 0.0: d=61
  seed 0 gives two wall loops; d=50 seed 1 a folded fan). Kept at a literal 60; a generator fix.
- Comments in `tests/test_properties_layout.py` still say "no `slow` marker" (task 1).
