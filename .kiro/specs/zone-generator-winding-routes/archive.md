# Archive — zone-generator-winding-routes

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 25 is winding routes** (lead, 2026-11-21, after the user's "continue ... keep working").
   It answers step 23's decision 6 follow-up: wind the whole route, so ramps wind, bends stop being
   square, and cave rooms can come back toward stock tunnel length.
2. **The path is stored, not re-derived** (A3). The clearance check needs the whole spec, so the
   readers take `CorridorSpec.path` rather than repeating it.

3. **The gate baseline for task 5 is 691/696** (lead, measured at `3871e84` with
   `EQ_PATH='F:\everquest_rof2'`, cave + warren, both layouts, 2-30 rooms, 2 seeds, `--seed 23`).
   The five failures are step 23's residuals (its archive "Follow-ups"). Without `EQ_PATH` the
   stock models leave the decor and the count is 695/696, so always sweep with it set.

## Follow-ups
