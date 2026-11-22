# Archive — zone-generator-winding-control

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 26 is a Winding scalar** (the user, 2026-11-21: "Windiness scalar", after the step 25
   look). One plan field scales the tunnel's wander; 1 is the stock-measured tunnel and stays
   byte-identical, 0 is straight. Turn sharpness and run lengths stay as measured.
2. **`WINDING_MAX` = 2, and the cave run grows by 2 widths for each unit of Winding above 1**
   (`layout.profile_run_factor`: 4 + 2(k − 1), so 4 at k ≤ 1 and k ≤ 1 keeps its bytes). The
   wander alone tops out by k ≈ 1.25: the heading cap (max_turn / 2) holds a run's stray to
   about 0.29 × its middle, not the clearance. Above 1, only a longer run leaves room to stray.
   c = 4 (run 8 at k = 2) and k = 3 at c = 2 (run 8) add a gate failure (1014, a decor throat).
   Measured over 40 cave graph builds (seeds 1000–1039) and 20 warren builds (seeds 1000–1019),
   8–30 rooms, verticality cycling, `EQ_PATH` set. Columns: rough corridors, share that winds
   (a path or a leg), share with a path, largest stray per corridor (u: p50, p90, mean),
   door-to-door p50 (u), gate passes (seed 1007 fails at every k and run, room_14's doors).

   | zone | run | k | rough | wind | path | p50 | p90 | mean | d2d | gate |
   |---|---|---|---|---|---|---|---|---|---|---|
   | cave | 4 | 0 | 657 | 0% | 0% | 0 | 0 | 0.00 | 104 | 39/40 |
   | cave | 4 | 0.5 | 657 | 61% | 56% | 0 | 3.1 | 0.63 | 102 | 39/40 |
   | cave | 4 | 1 | 657 | 61% | 56% | 0 | 5.8 | 1.13 | 102 | 39/40 |
   | cave | 4 | 1.5 | 657 | 61% | 56% | 0 | 6.0 | 1.20 | 102 | 39/40 |
   | cave | 4 | 2 | 657 | 61% | 56% | 0 | 6.0 | 1.20 | 102 | 39/40 |
   | cave | 4 | 3 | 657 | 61% | 56% | 0 | 6.0 | 1.20 | 102 | 39/40 |
   | **cave c=2** | **5** | **1.5** | 651 | 71% | 63% | 0 | 9.6 | 2.09 | 125 | 39/40 |
   | **cave c=2** | **6** | **2** | 647 | 73% | 73% | 0 | 9.9 | 2.38 | 148 | 39/40 |
   | cave c=2 | 8 | 3 | 652 | 79% | 73% | 4.9 | 14.8 | 6.20 | 194 | 38/40 |
   | cave c=4 | 6 | 1.5 | 647 | 73% | 73% | 0 | 9.9 | 2.38 | 148 | 39/40 |
   | cave c=4 | 8 | 2 | 652 | 79% | 73% | 4.9 | 14.8 | 6.20 | 194 | 38/40 |
   | cave c=4 | 12 | 3 | 652 | 84% | 74% | 10.9 | 23.7 | 11.82 | 287 | 39/40 * |
   | warren | 2 | 0 | 315 | 0% | 0% | 0 | 0 | 0.00 | 60 | 20/20 |
   | warren | 2 | 0.5–3 | 315 | 20% | 20% | 0 | 0 | 0.04–0.08 | 60 | 20/20 |

   \* 1007 passes there, but 1020 fails a corridor's headroom. Warren stray stays flat at
   0.08 u mean for k ≥ 1: its embed run (2 widths) leaves no room. The warren run is shared
   with non-rough dungeons, so it stays as it is (a follow-up if warrens should answer).

3. **Winding 2's three new gate failures were fixed at their root; the run growth stays**
   (task 4, the lead's call). Each was a place where a check passed what the gate fails:
   - `layout._straight_cor` (straightening a Bridge) judged its new route only against corridors
     leaving neither room, so a door could land on a door already on that wall (s432395022,
     open seam). It now judges every corridor, and two doors on one wall of a shared room stand
     a width plus a `U_DOOR_MARGIN` pier apart or at one point.
   - Decor's strict `walk` reading is now also read corner to corner: a one-cell diagonal lane
     the gate's own grid walks read shut (s2096692951, 476 u^2 cut).
   - Decor's clear-width targets count cells deep inside a Prop's plan as maybe free: the gate
     read a hollow rock's hole as the core (s770923935, throat_narrow).
   No golden moved. The gate is then 692/696 at Winding 0, 1 and 2: the hollow-Prop fix also
   clears step 23's warren graph moderate 25 s616736071 residual.

4. **First look: grid and square framed corridors, fixed at every setting** (the user,
   2026-11-21: "i think conceptually the winding is ok, but we have an issue where the rooms end up in a consistent grid layout with the 731402518 cave seed.  also some of the winding isn't as smooth as i would expect.  for the given seed 731402518, between room 9 and 11 is a sharper turn"; asked whether to keep Winding 1 byte-identical, chose "Every
   setting"). Causes: Graph `embed` places each neighbour centred one run off a wall and the
   springs hold it there (seed 731402518: rows and columns ~220 u apart); `measure_routes`
   skips a corridor holding a Transition line (`corr_11`, room_9 hewn to room_11), leaving
   square bends. Requirement 4 is amended; Requirements 7 and 8 added; tasks 8–11.

5. **The grid breaks in cave zones only, with straight doors** (task 8, the lead's call after a
   first attempt at every zone gave 36 failures, cost warrens loops and wound caves less). The
   switch is the cave style profile (`layout.JITTER_PROFILES`; the cave's graph rule set is
   `warren`, so it can't key on the rule set). Each edge is offset 0.4-1.0 of its slack (the
   half-extents across less 1.5 corridor widths) and its run spaced 1.25-1.75x, salted from
   room ids and sizes; jittered builds put both doors mid-span so the corridor runs straight,
   and keep U-route stair doors 3 u from a wall end. Built, hewn and warren zones keep their
   bytes. Cave graph seeds 1000-1039 at Winding 1: grid score mean 0.170 -> 0.065 (731402518:
   0.227 -> 0.030), wind 61% -> 69%, path 56% -> 60%, stray mean 1.13 -> 4.73 u, door to door
   p50 102 -> 118 u, gate 40/40.

6. **A framed rough corridor takes a path, its line fixed** (task 9, the lead's call). The path
   runs straight through the frame, breach or seam (depth plus a half-width each side; line
   position and `along_x` unchanged) and cuts or winds elsewhere; plain corridors still take
   their paths first. Cave graph seeds 1000-1039, Winding 1: framed corridors with a path
   0 -> 61 of 127, framed Z routes 0 -> 17 of 19. Moving a seam line to the hewn doorway
   (61 -> 109 of 127) was declined here: it changes how Transitions look.

## Follow-ups
- **Seam lines at the hewn doorway** would let 109 of 127 framed cave corridors wind (57 of 64
  split seams), against 61 with the line mid-corridor (task 9). A Transitions look change.
