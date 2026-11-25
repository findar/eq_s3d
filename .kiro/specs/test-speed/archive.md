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

## Follow-ups
