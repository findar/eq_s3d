# Archive — zone-generator-flooded-rooms

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Shallow water that ends at the doorway** (lead, 2026-11-20). The water line is 0.6 H over
   the floor. Corridors meet the room flush, so the water ends at the opening; a deep pool would
   show a wall of water there. Carrying the water into a corridor's ramp is a follow-up if the
   edge reads badly.
2. **Lava keeps its pool.** A `forge`'s lava region stays a box in the room's middle: a floor all
   lava could not be walked.

## Follow-ups
