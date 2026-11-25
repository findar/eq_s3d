# Archive — zone-generator-cave-clumps

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 29 is cave clumps and cave draw time** (the lead, 2026-11-25, on the user's "You
   pick step 27 followups"). Chosen from step 27's follow-ups because they answer the user's
   first-look words ("i would expect the potential for rooms to clump"): rooms opening
   straight into each other (stock 0.30 of edges, ours 0) and nearest-neighbour clumping
   (ours 1.39–1.64 median sides, stock 0.63), plus step 27's 2.7x cave draw time. Left in
   ROADMAP: outdoor loops under size variance, `dungeon_keep_clear`, the decor survey's open
   sky, the fortress's bigger rooms, the outdoor dungeon's lost stair.
2. **Throat: doors in line, 8 u wall to wall (12 u door to door; w = 18)** (task 2). 0 u fails
   `analyzer/traverse.py` `check_outline` (open seam), as do jogged doors up to 16 u; 4 u passes
   but Transitions give way 4x. Fix first: `layout.py` `_separate_rooms` holds every pair w + 1 apart.

## Follow-ups
