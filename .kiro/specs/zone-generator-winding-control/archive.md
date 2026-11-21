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

## Follow-ups
