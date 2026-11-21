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

## Follow-ups
