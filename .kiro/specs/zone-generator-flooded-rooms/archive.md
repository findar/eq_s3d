# Archive — zone-generator-flooded-rooms

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | A flooded room's water region covers the room up to a water line 0.6 H over its floor, re-seated on the final floor (`settle_floods`); a flat `liquid_water` (alpha, `FLAG_PASSABLE`) surface over every Outline Cell, its line read from the region (realised), not the Room_Type (advisory); the gate's wall and seam checks skip non-solid faces (`WalkSurface.solid`); decor's `_Mesh` reads the floor under the water | `169e985`, `3871e84` |
| 2 | The look, skipped at the user's word | — |

## Decisions

1. **Shallow water that ends at the doorway** (lead, 2026-11-20). The water line is 0.6 H over
   the floor. Corridors meet the room flush, so the water ends at the opening; a deep pool would
   show a wall of water there. Carrying the water into a corridor's ramp is a follow-up if the
   edge reads badly.
2. **Lava keeps its pool.** A `forge`'s lava region stays a box in the room's middle: a floor all
   lava could not be walked.

## Follow-ups
- **The water's edge at a doorway** (decision 1): not looked at in 3D. If it reads as a sheet
  hanging in the opening, carry the water a little way into the corridor's run-out.
- **No water texture in the 3D preview**: the GLB shows the water as a flat colour over the floor.
