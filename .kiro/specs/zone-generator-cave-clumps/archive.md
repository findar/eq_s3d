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
3. **Cave draw time accepted at 1.8x pre-step-27** (the lead, 2026-11-25, at task 1). Step 27's
   "25.7 s vs 9.5 s" was a total over 6 draws; per 30-room draw it was 3.94 s (pre-27 1.76 s), now
   3.21 s, placements float-equal. The 14 s bar is met; the rest (~2 s) is outside `embed.py`.
4. **Throats read as direct contacts** (the lead, at task 3): entry angle over non-throat ends
   (throat ends are square by design); 731402518 nn min 1.02 accepted (0.95 over 40 seeds); path
   shares over windable corridors.

## Follow-ups
- **Cave draw time outside `embed.py`** (task 1): ~1.7–2.1 s of a 30-room cave draw; profile it.
