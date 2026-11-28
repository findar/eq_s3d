# P-5 EverQuest look and feel — open items

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

IDs are `P-5-<k>`. The columns are explained in [P-1's `OPEN.md`](../P-1-web-app/OPEN.md). Roll-up: [`OPEN.md`](../../../OPEN.md).

## Requirements not served

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-5-1"></a>P-5-1 | Procedural normal maps and the preview's normal-map half ([ZG-Req-16](../../../.kiro/specs/zone-generator/requirements.md#requirement-16-procedural-normal-maps), [ZG-Req-17](../../../.kiro/specs/zone-generator/requirements.md#requirement-17-textured-preview)): nothing calls `Material.add_normal` | umbrella requirements; [umbrella decision 24](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) ([step 4](../../../.kiro/specs/zone-generator-interesting-textures/tasks.md)) | parked (user chose the classic look) | code: [`core/ter.py`](../../../core/ter.py) 122, no caller |
| <a id="p-5-2"></a>P-5-2 | The per-zone conformance report ([ZG-Req-15](../../../.kiro/specs/zone-generator/requirements.md#requirement-15-era-fidelity-and-measured-conformance); a planned `analyzer/conformance.py`; [Property 38](../../../.kiro/specs/zone-generator/design.md#property-38-conformance-is-measured-and-in-range)): never built; only textures are graded | umbrella design | open | code: no such module |
| <a id="p-5-3"></a>P-5-3 | Wilderness ground, water and tree textures (and their normal maps) | [step 4 archive](../../../.kiro/specs/zone-generator-interesting-textures/archive.md) (deferred) | open | record |

## Geometry and surfaces

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-5-4"></a>P-5-4 | Stairs come in two shapes (straight, Switchback) and all look alike: wanted spiral, N-landing, multi-level stair halls, and a form and finish by wall style and Purpose (a cave's smooth ramp, a fortress's dressed steps, a ruin's broken ones); stairs and Bridges stay square in caves | the user, 2026-11-22, in [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes); steps [8](../../../.kiro/specs/zone-generator-room-walls/archive.md) and [9](../../../.kiro/specs/zone-generator-room-layouts/archive.md) archives | open | code: [`generators/geometry.py`](../../../generators/geometry.py) 61 `StairPlan` |
| <a id="p-5-5"></a>P-5-5 | Lava rooms: the lava region is a box over 76% of the room up to at least 16 u, no surface, no pit; wanted a pool or channels below the floor with a source (seep, crack, sluice); also [`ai/expand.py`](../../../ai/expand.py) `_add_regions` | the user, 2026-11-22, in [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) | open | code: [`generators/semantics.py`](../../../generators/semantics.py) ~1011 |
| <a id="p-5-6"></a>P-5-6 | Every wilderness gets an interior lava patch whatever its theme (1–2 cells whenever the interior has 9+); make it themed and off by default | the user, 2026-11-22, in [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) | open | code: [`generators/wilderness/matrix.py`](../../../generators/wilderness/matrix.py) ~917 |
| <a id="p-5-7"></a>P-5-7 | Classic-layout caves keep box walls (no per-room finish on classic) | [step 21 archive](../../../.kiro/specs/zone-generator-cave/archive.md) | open | record |
| <a id="p-5-8"></a>P-5-8 | Built (non-rough) corridors, stairs and Bridges stay axis-aligned | [ROADMAP "Still open from M1"](../../../ROADMAP.md#-pick-up-here-next-session); [umbrella decision 42](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | open | code |
| <a id="p-5-9"></a>P-5-9 | Warrens don't answer Winding (byte-identical at 2 vs 1) and wind little (11 of 47); Z corridors only cut a diagonal; straight ones under ~80 u don't wind; U routes never wind | steps [25](../../../.kiro/specs/zone-generator-winding-routes/archive.md) and [26](../../../.kiro/specs/zone-generator-winding-control/archive.md) archives | open | record |
| <a id="p-5-10"></a>P-5-10 | Seam lines at the hewn doorway would let 109 of 127 framed cave corridors wind (61 today) | [step 26 archive](../../../.kiro/specs/zone-generator-winding-control/archive.md) | open | record |
| <a id="p-5-11"></a>P-5-11 | No water in an outdoor cave's flooded galleries (outdoor dungeons keep only the host landscape's regions) | [step 21 archive](../../../.kiro/specs/zone-generator-cave/archive.md) | open | record |
| <a id="p-5-12"></a>P-5-12 | The water is a flat colour in the preview | [step 24 archive](../../../.kiro/specs/zone-generator-flooded-rooms/archive.md) | open | record |
| <a id="p-5-13"></a>P-5-13 | Wilderness: the shoreline sits below the water level on some seeds ([`generators/wilderness/synth.py`](../../../generators/wilderness/synth.py)); the 150 u Design_Matrix cells and the 160 u fine cells drift apart (size half fixed in step 35 task 6, `a21413f`: Sizes are drawn in built units; positions still drift, matrix cell i centres at (i+0.5)·150 vs the terrain's (i+0.5)·160, so the terrain isn't centred on (0, 0); a 160 u matrix cell closes it and moves every World's bytes) | [ROADMAP](../../../ROADMAP.md) | open | record |
| <a id="p-5-14"></a>P-5-14 | Only one biome (plains); clustering for swamps, snow, hills, deserts and forests is recorded for when they come | [step 13 archive](../../../.kiro/specs/zone-generator-site-sockets/archive.md); [`styles/biomes.json`](../../../styles/biomes.json) | open | code |
| <a id="p-5-15"></a>P-5-15 | Style profiles are thin for cities (6 zones; cave 8) | [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) (it says 3–4 zones, now out of date) | open | code: [`styles/city.json`](../../../styles/city.json) |

## Caves

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-5-16"></a>P-5-16 | Cave corridors are dark; no decor or light in any winding tunnel | steps [22](../../../.kiro/specs/zone-generator-district-looks/archive.md) and [23](../../../.kiro/specs/zone-generator-winding-tunnels/archive.md) archives | open | record |
| <a id="p-5-17"></a>P-5-17 | Sparse cave Districts (three of six rooms bare; crystals outside the grotto) | [step 22 archive](../../../.kiro/specs/zone-generator-district-looks/archive.md) | open | record |
| <a id="p-5-18"></a>P-5-18 | A cave District can draw mostly `hewn` (seed 971456024: 1 rough, 5 hewn) against 80–85% rough measured | [step 22 archive](../../../.kiro/specs/zone-generator-district-looks/archive.md) | open | record |
| <a id="p-5-19"></a>P-5-19 | VSPBLOCK301 (a square cut slab) tagged rock; retagging it moves decor bytes in other themes, so it waits for a step allowed to | [step 21 archive](../../../.kiro/specs/zone-generator-cave/archive.md) | open | code: [`rules/decor/catalogue.json`](../../../rules/decor/catalogue.json) has `kind: rock` |

## Decor

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-5-20"></a>P-5-20 | Assemblies placed whole: pieces stock always places together, as Groups with stock's offsets | [step 11 archive](../../../.kiro/specs/zone-generator-room-decor/archive.md) | open | record |
| <a id="p-5-21"></a>P-5-21 | Wall Props sit into the wall on some outdoor-dungeon seeds (3, 4) and at corners; floor models along a wall assume a +X front | [step 11 archive](../../../.kiro/specs/zone-generator-room-decor/archive.md) | open | record |
| <a id="p-5-22"></a>P-5-22 | GENMETCRATE700 at twice stock size (the scale limit) | [step 11 archive](../../../.kiro/specs/zone-generator-room-decor/archive.md) | open | record |
| <a id="p-5-23"></a>P-5-23 | City decor near its band tops; city seed 53 under the per-room hard edge | steps [11](../../../.kiro/specs/zone-generator-room-decor/archive.md) and [12](../../../.kiro/specs/zone-generator-world-sockets/archive.md) archives | open | record |
| <a id="p-5-24"></a>P-5-24 | Later-era `.eqg` models (38,583 `.mod` names) and generated Props where the catalogue has nothing | [step 11 archive](../../../.kiro/specs/zone-generator-room-decor/archive.md) | open | record |
| <a id="p-5-25"></a>P-5-25 | The decor survey reads a zone's tallest room as open sky (city seed 11 drops its climax) | [step 27 archive](../../../.kiro/specs/zone-generator-random-placement/archive.md) | open | record |
| <a id="p-5-26"></a>P-5-26 | Stair and Bridge corridors get no decor (no RoomContext for treads and decks) | [step 12 archive](../../../.kiro/specs/zone-generator-world-sockets/archive.md) | open | code: [`generators/room_context.py`](../../../generators/room_context.py) 711 |
| <a id="p-5-27"></a>P-5-27 | Decor's dais fallback reads looser than the gate near walls | [step 26 archive](../../../.kiro/specs/zone-generator-winding-control/archive.md) | open | record |
| <a id="p-5-28"></a>P-5-28 | [`scripts/stage.py`](../../../scripts/stage.py) `decor_stage` uses the build's `BareCap` (since `f79d404`, which switched it over) but still doesn't `settle_room`, so its positions differ from a build's | [step 15 archive](../../../.kiro/specs/zone-generator-decor-rules/archive.md) | open | code: [`scripts/stage.py`](../../../scripts/stage.py) 427–444 |
| <a id="p-5-29"></a>P-5-29 | [`scripts/decor_room.py`](../../../scripts/decor_room.py) ignores Districts; the room view route takes one zone-wide `decor_layers` | [step 22 archive](../../../.kiro/specs/zone-generator-district-looks/archive.md) | open | code |
| <a id="p-5-30"></a>P-5-30 | Sites aren't in the room view | [step 15 archive](../../../.kiro/specs/zone-generator-decor-rules/archive.md) | open | record |
| <a id="p-5-31"></a>P-5-31 | The room view's first call in a fresh server is slow (re-measured 2026-11-17: 1.9–2.4 s plus 1.6 s import) | [step 15 archive](../../../.kiro/specs/zone-generator-decor-rules/archive.md) | parked (reopen if it recurs) | record |
| <a id="p-5-32"></a>P-5-32 | Boulders read as short pillars; a sunken court and rock columns wider at the foot | [step 9 archive](../../../.kiro/specs/zone-generator-room-layouts/archive.md) | parked (not asked for) | record |
| <a id="p-5-38"></a>P-5-38 | Decor cuts into a room floor: a cave classic dramatic 21-room build at seed 1866540615 fails the gate alone in a fresh process (decor footprint_cut 68 u²), and `--pair` seed 1985365888 (ice_keep room_11, see [P-2-6](../P-2-traversable/OPEN.md#p-2-6)) the same way. Moved from P-2-5: decor generation's problem, not cave generation's (the user, 2026-11-27: "decor cutting into floor is a decor generation problem, not a cave generation one so it's work that needs to be done when we refine the decor generation steps in teh future"). Off while decor defaults to none ([step 34](../../../.kiro/specs/zone-generator-decor-off/tasks.md)); for the decor refinement step | steps [30](../../../.kiro/specs/zone-generator-hall-length/archive.md), [31](../../../.kiro/specs/zone-generator-district-races/archive.md) archives | parked | record |

## Looks not taken

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-5-33"></a>P-5-33 | The water's edge at a doorway (if it reads as a sheet hanging in the opening, carry the water into the corridor's run-out) | [step 24 archive](../../../.kiro/specs/zone-generator-flooded-rooms/archive.md) | waiting | — |
| <a id="p-5-34"></a>P-5-34 | [Step 25](../../../.kiro/specs/zone-generator-winding-routes/tasks.md) task 5's fixes: the boss off the wall (case g), the dais top (case h) | [step 25 archive](../../../.kiro/specs/zone-generator-winding-routes/archive.md) | waiting | — |
| <a id="p-5-35"></a>P-5-35 | [Step 26](../../../.kiro/specs/zone-generator-winding-control/tasks.md) task 10: the dropped Bridges, the dais decor, a stalactite over s644918873 room_12's south door | [step 26 archive](../../../.kiro/specs/zone-generator-winding-control/archive.md) | waiting | — |
| <a id="p-5-36"></a>P-5-36 | [Step 29](../../../.kiro/specs/zone-generator-cave-clumps/tasks.md) (cave clumps): nothing looked at in 3D | [ROADMAP "Pick up here"](../../../ROADMAP.md#-pick-up-here-next-session), carried from step 29 | waiting | — |
| <a id="p-5-37"></a>P-5-37 | [Step 21](../../../.kiro/specs/zone-generator-cave/tasks.md) (caves): acceptance pass skipped at the user's word | [ROADMAP Done table](../../../ROADMAP.md#done) | waiting | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| GLB preview shows base colours, not textures ([umbrella Known Limitation 4](../../../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them), diffuse half) | [step 3](../../../.kiro/specs/zone-generator-placeholder-textures/tasks.md) (merge `7201ae3`, step 3 task 4: the textured GLB) |
| Race scale values are relative placeholders (`RACE_SCALE`; [umbrella Known Limitation 3](../../../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them)) | `e5c3601` ([step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) task 17: rooms sized from the race's body height H) |
| Outdoor terrain is just ground: no cliffs, boulders or vegetation | [step 1](../../../.kiro/specs/zone-generator-wilderness/tasks.md) (cliffs, water, lava), [step 2](../../../.kiro/specs/zone-generator-wilderness-trees/tasks.md) (trees; merge `b2913d2`, step 2 task 12: acceptance and timing), [step 10](../../../.kiro/specs/zone-generator-wilderness-pois/tasks.md) (Sites) |
| Water and mixed zones: outdoor + water; a cave mouth in a hillside | [step 1](../../../.kiro/specs/zone-generator-wilderness/tasks.md) (water plane, `AWT`); [step 5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md) (outdoor dungeon) |
| Cave ceilings drop with the cave size shift | [step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md) ([umbrella decision 41](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part A3: footprints shrink, not heights) |
| A cave District in another theme's zone gets no cave decor; after a built District it gets built walls | [step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md) (District looks) |
| Warm light, wall torches and treasure dressing in cave builds | [step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md) ([umbrella decision 41](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part A2) |
| A flooded room's water is a square in its middle | [step 24](../../../.kiro/specs/zone-generator-flooded-rooms/tasks.md) |
| Wind the whole route, not each leg; cave rooms twice as far apart | [step 25](../../../.kiro/specs/zone-generator-winding-routes/tasks.md) (rooms 4 corridor widths apart) |
| A windiness scalar | [step 26](../../../.kiro/specs/zone-generator-winding-control/tasks.md) |
| Rooms opening straight into each other (stock 0.30 of edges) | [step 29](../../../.kiro/specs/zone-generator-cave-clumps/tasks.md) |
| Corridor lights: no corridor RoomContexts | `c498ef0` ([step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) task 14: corridor RoomContexts, so decor lights corridors) |
| The tomb layer does nothing outside a tomb | [step 15 decision 5](../../../.kiro/specs/zone-generator-decor-rules/archive.md#decisions) (struck through in its archive) |
| Natural geometry style ([M5](../../../.kiro/specs/zone-generator/design.md#delivery-plan) `natural.py`) | superseded by [step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md)'s `rough` style ([umbrella decision 28](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)) |
| Light-density stat reads 0 in profiles | not a bug (stock zones are lit by placed light models); kept as a note in this pillar's DESIGN |
