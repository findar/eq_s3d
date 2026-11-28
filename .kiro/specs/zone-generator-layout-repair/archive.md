# Archive — zone-generator-layout-repair

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 33 is layout check-and-repair, measured first; step 32 is paused** (the lead, 2026-11-27, on the user's
   "can we pause the step 32 work and focus on that if it should improve our build times?"). Both own
   `generators/layout.py`; step 32 task 1 is parked on `agent/followups-1` and resumes after this step.

## Follow-ups
- Loops-first planning (designed one-way loops) and corridors as placed blocks: later slices, after task 3.
