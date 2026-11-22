# Archive — zone-generator-winding-control

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | `ZonePlan.winding` (0..`WINDING_MAX`, default 1) reaches `ZoneSpec.winding`; the tunnel's wander is scaled for measure, mesh, decor, map and gate | `c120210`, `ff88226` |
| 2 | `WINDING_MAX` 2; the cave run grows 2 widths per unit above 1 (decision 2) | `90278e9` |
| 3 | Winding slider (dungeon, city, outdoor dungeon), planner words, LLM schema text | `8b55240`, `a73fe84` |
| 4 | Gate 692/696 at 0/1/2; a straightened Bridge keeps off doors, decor reads diagonal lanes and hollow Props | `7149e01`, `70521d1`, `948d9cc` |
| 5 | `docs/ACCEPTANCE.md` "Step 26 — Winding control"; thorough 4082 passed | `e17a1ad` |
| 6 | First look: grid and a square framed corridor (decision 4); second look "it looks good" | `d40b02c` |
| 8 | Cave Graph rooms leave the lattice, facing pairs run straight (decision 5) | `b6085d8` |
| 9 | Framed rough corridors take a path, straight through the line (decision 6) | `d32e19a`, `fc671b8` |
| 10 | Hairline outline link, Bridge slot vs door, decor on a dais fixed; gate 693/696 at 0/1/2, bands < 5%, suite 4100 passed (decision 7) | `7566697`, `131f3a2`, `74ae74e` |
| 11 | ACCEPTANCE X.7, first-look fixes built and quoted | `2a0a6b3` |

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

7. **Task 8's layouts exposed three faults, fixed at their root** (task 10, the lead's call; the
   >= 692 target kept). `outline._link`: a gap under `SNAP` to the Core is touching, not a
   hairline link (s937463091). `_mark_bridges` (jittered builds): no Bridge whose slot meets a
   door's in-room piece on the bridged room's wall (s2071938654). Decor `_wide_doors` aims where
   the gate does (cells within 4 u of the room floor) and, when no door reads wide, re-reads at
   the gate's radius (s644918873, a dais). No golden moved. Gate 693/696 at Winding 0, 1 and 2
   (three residuals; cave graph flat 29 s1259910114 now passes); bands under 5% (worst cave
   classic dramatic 4.0%); full suite 4100 passed.

8. **Second look accepted** (user, 2026-11-22): "i would say it looks good but a future task should also adjust length of halls and also when we generate rooms they should end up randomly positioned and connected". Hall length and random
   placement are follow-ups, not part of this step.

## Follow-ups
- **Hall length control** (the user, at the second look): a way to adjust how long corridors
  run, alongside Winding (today only the cave run grows with Winding above 1).
- **Randomly positioned, connected rooms** (the user, at the second look): rooms should land at
  random positions and still connect, beyond task 8's cave-only jitter (built, hewn and warren
  Graph zones still sit on the lattice; the classic layout's placement not reviewed for this).
- **Warrens don't answer Winding** (task 5: byte-identical at 2 vs 1).
- **`ZONE_PLAN_JSON_SCHEMA` lacks `winding`** (the LLM planner gets it as prompt text only).
- **Gate residuals:** three footprint cuts (warren classic flat 23 s490919952, warren classic
  flat 26 s1205085953, cave classic moderate 8 s1728424002).
- **Not looked at in 3D:** task 10's dropped Bridges and the dais decor; a stalactite over
  s644918873 room_12's south door (X.7.3).
- **Decor's dais fallback reads looser than the gate** near walls; it only applies to rooms
  that checked nothing before (task 10).
- **Seam lines at the hewn doorway** would let 109 of 127 framed cave corridors wind (57 of 64
  split seams), against 61 with the line mid-corridor (task 9). A Transitions look change.
