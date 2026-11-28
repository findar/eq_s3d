# P-G Engaging every time — open items

Status and Checked as in [P-A's OPEN](../P-A-web-app/OPEN.md). Roll-up: [OPEN.md](../../../OPEN.md).

## Requirements and the user's calls

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| G-1 | Requirement 22, topology control (linear, branching, looped; "maze" and "linear" words): never built | umbrella Req 22; decision 10 | waiting (still wanted, given Graph rule sets?) | code: no `topology` on `ZonePlan` |
| G-2 | Districts on by default for 8+ rooms? | step 20 (decision 39 A1) | waiting | — |
| G-3 | Wilderness size: every wilderness is 2400 u, outdoor dungeons 1200 u; a Size range from stock, random when unset, maybe non-square | step 10 (the user's word to start) | waiting | code: `generators/wilderness/matrix.py` 392 |
| G-4 | Other ways into an outdoor dungeon: the Tunnel is one terrain cell wide into a hill; wanted a wide flaring Mouth, and sinkholes, ravines, ruin stairs, cliff openings, wells | user 2026-11-22 | open | code: `generators/outdoor_dungeon.py` `Entrance` |
| G-5 | One-way walls (the `layout-oneway-connections` follow-on): drops landed in step 31; one-way passages realised by doors did not | umbrella design "Scope of open task files" | open | code |

## Districts and races

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| G-6 | Pairs with 2+ links fell from 82% to 68%; place intruder rooms nearer host walls | step 31 archive | in flight (step 32 task 1, step 33 Req 4) | — |
| G-7 | Dramatic Levels and `_resolve_conflicts` can leave an intrusion with no breach (prompt seeds 2023, 2024) | step 31 archive | open | record |
| G-8 | Drops into the goblins are short (7–13 u) | ROADMAP carried from step 31 | open | record |
| G-9 | Classic zones' breaches have no `breach` form and no rough break | step 31 archive | open | record |
| G-10 | A third District gets breached too (`breach_hosts` takes every non-Threshold cross link); those zones already run over stock's decor band | step 31 archive | open | record |
| G-11 | Similar light across some Threshold pairs (tomb and sunken_ruin both cool blue) | step 20 archive | open | record |
| G-12 | A repeated Purpose alternates as built / abandoned / as built; `ruined` never appears | step 20 archive | open | record |
| G-13 | A second cave District gets no crystal grotto boss; a crystal grotto can stand as a dead end (seed 1840275513) | step 22 archive | open | record |
| G-14 | `layout.rooms.<id>.district` reads 0 in districted zones (`rooms[*].district` is right) | step 22 archive | open | record |

## Layout and scale

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| G-15 | A low stacking room type (crawlway, cellar, gallery): stock stacks low rooms ~28 u apart; our Levels are ~135 u | steps 7, 8, 9 archives | open | record |
| G-16 | Cities share dungeon geometry at stock scale; they need their own sizing or layout (streets, plazas) and room types (tavern, home, shop) | steps 7, 11 archives | open | record |
| G-17 | A dragon's stairs are very long (2 u risers over ~250 u Levels) | step 7 archive | open | record |
| G-18 | Dramatic is only somewhat more than Moderate (2.70 vs 2.33 Levels at 12 rooms) | step 7 archive | open | record |
| G-19 | Outdoor dungeons rarely reach three Levels (the hill's depth limits them) | step 7 archive | open | record |
| G-20 | Giant and dragon outdoor dungeons drop rooms (giants keep all rooms in 4–6 of 20 seeds); a host sized to the race would fit them | steps 5, 7 archives | open | record |
| G-21 | Height bands overlap at the top (a human's tallest hall over a dragon's lowest room) | step 7 archive | parked (footprints still separate) | record |
| G-22 | Rule-format gaps: no wildcard kind in matches; `reattach` can't pick a side; edge-only rules spend no stage budget; sizes on kept nodes ignored | step 6 archive | open | code: no wildcard in `generators/topology/ruleset.py` |
| G-23 | Warren bands rest on one stock zone (blackburrow) | step 6 archive | open | record |
| G-24 | Outdoor loop corridors lost to bigger rooms (fidelity 0.925 → 0.905) | step 27 archive | open | record |
| G-25 | Fit `dungeon_keep_clear` to the rooms so big halls under a hill leave ground for Sites | step 27 archive | open | record |
| G-26 | The fortress's bigger median room (17.7 H, a 156 u storeroom); an outdoor dungeon's lost stair | ROADMAP carried from step 27 | open | record |
| G-27 | Caves: built stairs 135 → 143 over 41 seeds; cave Graph flat quality fails 3.8% → 5.0%; the entrance clump at seed 731402518 nearly in a row | ROADMAP carried from step 29 | open | record |
| G-28 | Outdoor halls stop at ~1.6× and don't shorten below 1 | step 30 archive | parked (the hill caps it) | record |

## Sites

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| G-29 | Site weights against a stock kind survey (farmsteads 13% vs ~27%, ruins 11% vs ~1%) | step 13 archive | open | record |
| G-30 | Outdoor-dungeon points favour small recipes (farmsteads fit on 1 of 39 seeds) | step 13 archive | open | record |
| G-31 | Dense gathers less than Normal | step 13 archive (its decision 11) | open | record |
| G-32 | A farmstead often loses its barn (5 of 20 seeds at Normal); the survey splits a farmstead in two on seeds 1001 and 1004 | steps 10, 13 archives | open | record |
| G-33 | `altar_stone` is built but no recipe places it | step 10 archive | open | code: only `[structures.altar_stone]` in `rules/sites/sites.toml` |

## Looks not taken

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| L-1 | Step 19: the quality banner has not been looked at by the user | step 19 archive | waiting | — |
| L-2 | Step 20: the palette and light change across a Threshold in 3D | step 20 archive | waiting | — |
| L-3 | Step 22 (District looks): nothing looked at in 3D | ROADMAP carried from step 22 | waiting | — |
| L-7 | Step 27 tasks 9–13: angled openings, long straight tunnels aimed at a room centre, held lines through frames | step 27 archive | waiting | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| Sites spread at random where stock plains cluster them; outdoor dungeons got Sites on only some seeds | step 13 (site-sockets tasks 3–7, 11) |
| `outdoor_dungeon.keep_clear_shapes` duplicates `stages.entrance_keep_clear` | `570ff4f` (step 13 task 7) |
| Verticality for outdoor dungeons (step 5) | step 7, merge `1f5a74a` |
| Big-race outdoor dungeons never plan (step 5) | ogres by `e5c3601` (step 7 task 17); giants and dragons now plan with rooms dropped (G-20) |
| Stacked rooms; room shapes; room kinds don't show (step 6) | steps 7 and 8 |
| The district look (steps 6, 8) | step 22 |
| A Hall length control; randomly positioned, connected rooms (step 26) | steps 30 and 27 |
| Per-district hall length, a race per District, intruders, drops (step 30) | step 31 |
| Same seed, different build when another zone was built first in the process (step 31) | `6781622` (step 32 task 2) |
| Outdoor "rooms" only set terrain bounds (ROADMAP "Outdoor rooms as real places") | superseded by wilderness Sites (step 10) |
