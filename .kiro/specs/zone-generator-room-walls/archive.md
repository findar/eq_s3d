# Archive — zone-generator-room-walls

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 16).

## Decisions

The design's "Decisions" section stands. The user took the recommended answer to every open question on 2026-11-06:

1. The styles are `built`, `hewn` and `rough`.
2. One style per zone, with rules able to fix a shape; a mix by district is a follow-up.
3. The Classic engine stays rectangles, byte-identical.
4. Whether shaped rooms grow to keep their floor area is decided in task 13, from task 12's measure and the first look.
5. Stairs and bridges stay as built in this step; check them at the first look.
6. `built` rooms change too (L-shapes, crosses, alcoves, cut corners, some plain rectangles); every Graph build changes once, its goldens recaptured with old and new hashes.

- **What the survey changed (task 1, 2026-11-06):** Outlines take off about 5–20% of the Box (true Fill 0.80–0.95), because all-rectangle builds measure 0.78–0.81 on the survey's Fill and stock measures 0.64–0.75. Plain rectangles stay `built`'s commonest shape, with a new `cut` shape (corners cut) next. Rough Cells are about 5 H, hewn about 8 H, built modules about 4 H. Mixed zones are left out of the bands.

## Follow-ups

Carried in from earlier steps and relevant here:

- **Room kinds don't show** (step 6): answered here through each style's shapes table.
- **Low stacking room type** (step 7): stock stacks low rooms, and `hewn` or `rough` low galleries are a natural place for it. Not in this step.
- **The district look** (step 6): one style per zone in this step (Open question 2). Task 1 found stock zones often mix built and cave parts (chardok, cazicthule, hole, gukbottom's temple, soldungb's wing), so a mix by district is the natural next step.
