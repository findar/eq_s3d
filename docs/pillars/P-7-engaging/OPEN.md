# P-7 Engaging every time — open items

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

IDs are `P-7-<k>`. The columns are explained in [P-1's `OPEN.md`](../P-1-web-app/OPEN.md). Roll-up: [`OPEN.md`](../../../OPEN.md).

## Requirements and the user's calls

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-7-1"></a>P-7-1 | [P-7-Req-2](PLAN.md#p-7-req-2), topology control (linear, branching, looped; the words "maze" and "linear"): never built | [ZG-Req-22](../../../.kiro/specs/zone-generator/requirements.md#requirement-22-topology-control); [umbrella decision 10](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | waiting (still wanted, given Graph rule sets?) | code: no `topology` on `ZonePlan` |
| <a id="p-7-2"></a>P-7-2 | Districts on by default for 8+ rooms? | [step 20 archive](../../../.kiro/specs/zone-generator-districts/archive.md) ([umbrella decision 39](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part A1) | waiting | — |
| <a id="p-7-3"></a>P-7-3 | Wilderness size: every wilderness is 2400 u, outdoor dungeons 1200 u; a Size range from stock, random when unset, maybe non-square | [step 10 archive](../../../.kiro/specs/zone-generator-wilderness-pois/archive.md) (it waits on the user's word to start) | waiting | code: [`generators/wilderness/matrix.py`](../../../generators/wilderness/matrix.py) 392 |
| <a id="p-7-4"></a>P-7-4 | Other ways into an outdoor dungeon: the Tunnel is one terrain cell wide into a hill; wanted a wide flaring Mouth, and sinkholes, ravines, ruin stairs, cliff openings, wells | the user, 2026-11-22, in [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) | open | code: [`generators/outdoor_dungeon.py`](../../../generators/outdoor_dungeon.py) `Entrance` |
| <a id="p-7-5"></a>P-7-5 | One-way walls (the `layout-oneway-connections` follow-on): drops landed in [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md); one-way passages realised by doors did not | umbrella design, [Scope of open task files](../../../.kiro/specs/zone-generator/design.md#scope-of-open-task-files) | open | code |

## Districts and races

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-7-6"></a>P-7-6 | Pairs with 2+ links fell from 82% to 68%; place intruder rooms nearer host walls | [step 31 archive](../../../.kiro/specs/zone-generator-district-races/archive.md) | in flight ([step 32](../../../.kiro/specs/zone-generator-races-followups/tasks.md) task 1; [S-33-Req-4](../../../.kiro/specs/zone-generator-layout-repair/requirements.md#requirements)) | — |
| <a id="p-7-7"></a>P-7-7 | Dramatic Levels and `_resolve_conflicts` can leave an intrusion with no breach (prompt seeds 2023, 2024) | [step 31 archive](../../../.kiro/specs/zone-generator-district-races/archive.md) | open | record |
| <a id="p-7-8"></a>P-7-8 | Drops into the goblins are short (7–13 u) | [ROADMAP "Pick up here"](../../../ROADMAP.md#-pick-up-here-next-session), carried from [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) | open | record |
| <a id="p-7-9"></a>P-7-9 | Classic zones' breaches have no `breach` form and no rough break | [step 31 archive](../../../.kiro/specs/zone-generator-district-races/archive.md) | open | record |
| <a id="p-7-10"></a>P-7-10 | A third District gets breached too (`breach_hosts` takes every non-Threshold cross link); those zones already run over stock's decor band | [step 31 archive](../../../.kiro/specs/zone-generator-district-races/archive.md) | open | record |
| <a id="p-7-11"></a>P-7-11 | Similar light across some Threshold pairs (tomb and sunken_ruin both cool blue) | [step 20 archive](../../../.kiro/specs/zone-generator-districts/archive.md) | open | record |
| <a id="p-7-12"></a>P-7-12 | A repeated Purpose alternates as built / abandoned / as built; `ruined` never appears | [step 20 archive](../../../.kiro/specs/zone-generator-districts/archive.md) | open | record |
| <a id="p-7-13"></a>P-7-13 | A second cave District gets no crystal grotto boss; a crystal grotto can stand as a dead end (seed 1840275513) | [step 22 archive](../../../.kiro/specs/zone-generator-district-looks/archive.md) | open | record |
| <a id="p-7-14"></a>P-7-14 | `layout.rooms.<id>.district` reads 0 in districted zones (`rooms[*].district` is right) | [step 22 archive](../../../.kiro/specs/zone-generator-district-looks/archive.md) | open | record |

## Layout and scale

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-7-15"></a>P-7-15 | A low stacking room type (crawlway, cellar, gallery): stock stacks low rooms ~28 u apart; our Levels are ~135 u | steps [7](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md), [8](../../../.kiro/specs/zone-generator-room-walls/archive.md) and [9](../../../.kiro/specs/zone-generator-room-layouts/archive.md) archives | open | record |
| <a id="p-7-16"></a>P-7-16 | Cities share dungeon geometry at stock scale; they need their own sizing or layout (streets, plazas) and room types (tavern, home, shop) | steps [7](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md) and [11](../../../.kiro/specs/zone-generator-room-decor/archive.md) archives | open | record |
| <a id="p-7-17"></a>P-7-17 | A dragon's stairs are very long (2 u risers over ~250 u Levels) | [step 7 archive](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md) | open | record |
| <a id="p-7-18"></a>P-7-18 | Dramatic is only somewhat more than Moderate (2.70 vs 2.33 Levels at 12 rooms) | [step 7 archive](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md) | open | record |
| <a id="p-7-19"></a>P-7-19 | Outdoor dungeons rarely reach three Levels (Dramatic 5/8/12 rooms: 0/1/2 of 30 after step 35 task 4). Not the hill: `GraphEngine._descending` takes the first one-way graph and sets every room above the entrance to Level 0; it should prefer or grow graphs that reach three Levels at Dramatic | [step 7 archive](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md) | open | record |
| <a id="p-7-20"></a>P-7-20 | Giant and dragon outdoor dungeons drop rooms (giants keep all rooms in 4–6 of 20 seeds); a host sized to the race would fit them | steps [5](../../../.kiro/specs/zone-generator-outdoor-dungeon/archive.md) and [7](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md) archives | open | record |
| <a id="p-7-21"></a>P-7-21 | Height bands overlap at the top (a human's tallest hall over a dragon's lowest room) | [step 7 archive](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md) | parked (footprints still separate) | record |
| <a id="p-7-22"></a>P-7-22 | Rule-format gaps: no wildcard kind in matches; `reattach` can't pick a side; edge-only rules spend no stage budget; sizes on kept nodes ignored | [step 6 archive](../../../.kiro/specs/zone-generator-graph-layout/archive.md) | open | code: no wildcard in [`generators/topology/ruleset.py`](../../../generators/topology/ruleset.py) |
| <a id="p-7-23"></a>P-7-23 | Warren bands rest on one stock zone (blackburrow) | [step 6 archive](../../../.kiro/specs/zone-generator-graph-layout/archive.md) | open | record |
| <a id="p-7-24"></a>P-7-24 | Outdoor loop corridors lost to bigger rooms (fidelity 0.925 → 0.905) | [step 27 archive](../../../.kiro/specs/zone-generator-random-placement/archive.md) | open | record |
| <a id="p-7-25"></a>P-7-25 | Fit `dungeon_keep_clear` to the rooms so big halls under a hill leave ground for Sites | [step 27 archive](../../../.kiro/specs/zone-generator-random-placement/archive.md) | open | record |
| <a id="p-7-26"></a>P-7-26 | The fortress's bigger median room (17.7 H, a 156 u storeroom); an outdoor dungeon's lost stair | [ROADMAP "Pick up here"](../../../ROADMAP.md#-pick-up-here-next-session), carried from [step 27](../../../.kiro/specs/zone-generator-random-placement/tasks.md) | open | record |
| <a id="p-7-27"></a>P-7-27 | Caves: built stairs 135 → 143 over 41 seeds; cave Graph flat quality fails 3.8% → 5.0%; the entrance clump at seed 731402518 nearly in a row | [ROADMAP "Pick up here"](../../../ROADMAP.md#-pick-up-here-next-session), carried from [step 29](../../../.kiro/specs/zone-generator-cave-clumps/tasks.md) | open | record |
| <a id="p-7-28"></a>P-7-28 | Outdoor halls stop at ~1.6× and don't shorten below 1 | [step 30 archive](../../../.kiro/specs/zone-generator-hall-length/archive.md) | parked (the hill caps it) | record |

## Sites

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-7-29"></a>P-7-29 | Site weights against a stock kind survey (farmsteads 13% vs ~27%, ruins 11% vs ~1%) | [step 13 archive](../../../.kiro/specs/zone-generator-site-sockets/archive.md) | open | record |
| <a id="p-7-30"></a>P-7-30 | Outdoor-dungeon points favour small recipes (farmsteads fit on 1 of 39 seeds) | [step 13 archive](../../../.kiro/specs/zone-generator-site-sockets/archive.md) | open | record |
| <a id="p-7-31"></a>P-7-31 | Dense gathers less than Normal | [step 13 archive](../../../.kiro/specs/zone-generator-site-sockets/archive.md) ([step 13 decision 11](../../../.kiro/specs/zone-generator-site-sockets/archive.md#decisions)) | open | record |
| <a id="p-7-32"></a>P-7-32 | A farmstead often loses its barn (5 of 20 seeds at Normal); the survey splits a farmstead in two on seeds 1001 and 1004 | steps [10](../../../.kiro/specs/zone-generator-wilderness-pois/archive.md) and [13](../../../.kiro/specs/zone-generator-site-sockets/archive.md) archives | open | record |
| <a id="p-7-33"></a>P-7-33 | `altar_stone` is built but no recipe places it | [step 10 archive](../../../.kiro/specs/zone-generator-wilderness-pois/archive.md) | open | code: only `[structures.altar_stone]` in [`rules/sites/sites.toml`](../../../rules/sites/sites.toml) |

## Looks not taken

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-7-34"></a>P-7-34 | [Step 19](../../../.kiro/specs/zone-generator-quality/tasks.md): the quality banner has not been looked at by the user | [step 19 archive](../../../.kiro/specs/zone-generator-quality/archive.md) | waiting | — |
| <a id="p-7-35"></a>P-7-35 | [Step 20](../../../.kiro/specs/zone-generator-districts/tasks.md): the palette and light change across a Threshold in 3D | [step 20 archive](../../../.kiro/specs/zone-generator-districts/archive.md) | waiting | — |
| <a id="p-7-36"></a>P-7-36 | [Step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md) (District looks): nothing looked at in 3D | [ROADMAP "Pick up here"](../../../ROADMAP.md#-pick-up-here-next-session), carried from step 22 | waiting | — |
| <a id="p-7-37"></a>P-7-37 | [Step 27](../../../.kiro/specs/zone-generator-random-placement/tasks.md) tasks 9–13: angled openings, long straight tunnels aimed at a room centre, held lines through frames | [step 27 archive](../../../.kiro/specs/zone-generator-random-placement/archive.md) | waiting | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| Sites spread at random where stock plains cluster them; outdoor dungeons got Sites on only some seeds | [step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) (its tasks 3 to 7 and 11) |
| `outdoor_dungeon.keep_clear_shapes` duplicates `stages.entrance_keep_clear` | `570ff4f` ([step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) task 7: the outdoor dungeon keeps its rooms clear, not its whole hill) |
| Verticality for outdoor dungeons ([step 5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md)) | [step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) (merge `1f5a74a`, step 7 task 7: outdoor dungeons go down through Levels) |
| Big-race outdoor dungeons never plan ([step 5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md)) | ogres by `e5c3601` ([step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) task 17: rooms sized for their race); giants and dragons now plan with rooms dropped ([P-7-20](#p-7-20)) |
| Stacked rooms; room shapes; room kinds don't show ([step 6](../../../.kiro/specs/zone-generator-graph-layout/tasks.md)) | steps [7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) and [8](../../../.kiro/specs/zone-generator-room-walls/tasks.md) |
| The district look (steps [6](../../../.kiro/specs/zone-generator-graph-layout/tasks.md), [8](../../../.kiro/specs/zone-generator-room-walls/tasks.md)) | [step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md) |
| A Hall length control; randomly positioned, connected rooms ([step 26](../../../.kiro/specs/zone-generator-winding-control/tasks.md)) | steps [30](../../../.kiro/specs/zone-generator-hall-length/tasks.md) and [27](../../../.kiro/specs/zone-generator-random-placement/tasks.md) |
| Per-district hall length, a race per District, intruders, drops ([step 30](../../../.kiro/specs/zone-generator-hall-length/tasks.md)) | [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) |
| Same seed, different build when another zone was built first in the process ([step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md)) | `6781622` ([step 32](../../../.kiro/specs/zone-generator-races-followups/tasks.md) task 2: the stock model cache is keyed by actor, not mesh) |
| Outdoor "rooms" only set terrain bounds ([ROADMAP "Design work captured"](../../../ROADMAP.md#design-work-captured-not-yet-built), "Outdoor rooms as real places") | superseded by wilderness Sites ([step 10](../../../.kiro/specs/zone-generator-wilderness-pois/tasks.md)) |
