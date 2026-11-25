# Archive — test-speed

## What landed

| Tasks | What landed | Commits |
|---|---|---|

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

## Follow-ups
- Comments in `tests/test_properties_layout.py` still say "no `slow` marker" (task 1).
