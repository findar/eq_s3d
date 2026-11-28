# P-E EverQuest look and feel — open items

Status and Checked as in [P-A's OPEN](../P-A-web-app/OPEN.md). Roll-up: [OPEN.md](../../../OPEN.md).

## Requirements not served

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| E-1 | Procedural normal maps and the preview's normal half (Req 16, 17.2–17.3): nothing calls `Material.add_normal` | umbrella; step 4 decision 24 | parked (user chose the classic look) | code: `core/ter.py` 122, no caller |
| E-2 | The per-zone ConformanceReport (Req 15, `analyzer/conformance.py`, Property 38): never built; only textures are graded | umbrella design | open | code: no such module |
| E-3 | Wilderness ground, water and tree textures (and their normal maps) | step 4 (deferred) | open | record |

## Geometry and surfaces

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| E-4 | Stairs come in two shapes (straight, Switchback) and all look alike: wanted spiral, N-landing, multi-level stair halls, and a form and finish by wall style and Purpose (a cave's smooth ramp, a fortress's dressed steps, a ruin's broken ones); stairs and Bridges stay square in caves | user 2026-11-22; steps 8, 9 | open | code: `generators/geometry.py` 61 `StairPlan` |
| E-5 | Lava rooms: the lava region is a box over 76% of the room up to at least 16 u, no surface, no pit; wanted a pool or channels below the floor with a source (seep, crack, sluice); also `ai/expand.py` `_add_regions` | user 2026-11-22 | open | code: `generators/semantics.py` ~1011 |
| E-6 | Every wilderness gets an interior lava patch whatever its theme (1–2 cells whenever the interior has 9+); make it themed and off by default | user 2026-11-22 | open | code: `generators/wilderness/matrix.py` ~917 |
| E-7 | Classic-layout caves keep box walls (no per-room finish on classic) | step 21 archive | open | record |
| E-8 | Built (non-rough) corridors, stairs and Bridges stay axis-aligned | ROADMAP "Still open from M1"; decision 42 | open | code |
| E-9 | Warrens don't answer Winding (byte-identical at 2 vs 1) and wind little (11 of 47); Z corridors only cut a diagonal; straight ones under ~80 u don't wind; U routes never wind | steps 25, 26 archives | open | record |
| E-10 | Seam lines at the hewn doorway would let 109 of 127 framed cave corridors wind (61 today) | step 26 archive | open | record |
| E-11 | No water in an outdoor cave's flooded galleries (outdoor dungeons keep only the host landscape's regions) | step 21 archive | open | record |
| E-12 | The water is a flat colour in the preview | step 24 archive | open | record |
| E-13 | Wilderness: shoreline below water level on some seeds (`synth.py`); the 150 u matrix vs 160 u fine-cell frame drift | ROADMAP | open | record |
| E-14 | Only one biome (plains); clustering for swamps, snow, hills, deserts and forests is recorded for when they come | step 13 archive; `styles/biomes.json` | open | code |
| E-15 | Style profiles are thin for cities (6 zones; cave 8) | ROADMAP (said 3–4, now stale) | open | code: `styles/city.json` |

## Caves

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| E-16 | Cave corridors are dark; no decor or light in any winding tunnel | steps 22, 23 archives | open | record |
| E-17 | Sparse cave Districts (three of six rooms bare; crystals outside the grotto) | step 22 archive | open | record |
| E-18 | A cave District can draw mostly `hewn` (seed 971456024: 1 rough, 5 hewn) against 80–85% rough measured | step 22 archive | open | record |
| E-19 | VSPBLOCK301 (a square cut slab) tagged rock; retagging it moves decor bytes in other themes, so it waits for a step allowed to | step 21 archive | open | code: catalogue `kind: rock` |

## Decor

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| E-20 | Assemblies placed whole: pieces stock always places together, as Groups with stock's offsets | step 11 archive | open | record |
| E-21 | Wall Props sit into the wall on some outdoor-dungeon seeds (3, 4) and at corners; floor models along a wall assume a +X front | step 11 archive | open | record |
| E-22 | GENMETCRATE700 at twice stock size (the scale limit) | step 11 archive | open | record |
| E-23 | City decor near its band tops; city seed 53 under the per-room hard edge | steps 11, 12 archives | open | record |
| E-24 | Later-era `.eqg` models (38,583 `.mod` names) and generated Props where the catalogue has nothing | step 11 archive | open | record |
| E-25 | The decor survey reads a zone's tallest room as open sky (city seed 11 drops its climax) | step 27 archive | open | record |
| E-26 | Stair and Bridge corridors get no decor (no RoomContext for treads and decks) | step 12 archive | open | code: `generators/room_context.py` 711 |
| E-27 | Decor's dais fallback reads looser than the gate near walls | step 26 archive | open | record |
| E-28 | `scripts/stage.py` `decor_stage` uses the build's `BareCap` (`f79d404`) but still doesn't `settle_room`, so its positions differ from a build's | step 15 archive | open | code: `scripts/stage.py` 427–444 |
| E-29 | `scripts/decor_room.py` ignores Districts; the room view route takes one zone-wide `decor_layers` | step 22 archive | open | code |
| E-30 | Sites aren't in the room view | step 15 archive | open | record |
| E-31 | The room view's first call in a fresh server is slow (re-measured 2026-11-17: 1.9–2.4 s plus 1.6 s import) | step 15 archive | parked (reopen if it recurs) | record |
| E-32 | Boulders read as short pillars; a sunken court and rock columns wider at the foot | step 9 archive | parked (not asked for) | record |

## Looks not taken

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| L-4 | The water's edge at a doorway (if it reads as a sheet hanging in the opening, carry the water into the corridor's run-out) | step 24 archive | waiting | — |
| L-5 | Step 25 task 5's fixes: the boss off the wall (case g), the dais top (case h) | step 25 archive | waiting | — |
| L-6 | Step 26 task 10: the dropped Bridges, the dais decor, a stalactite over s644918873 room_12's south door | step 26 archive | waiting | — |
| L-8 | Step 29 (cave clumps): nothing looked at in 3D | ROADMAP carried from step 29 | waiting | — |
| L-9 | Step 21 (caves): acceptance pass skipped at the user's word | ROADMAP | waiting | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| GLB preview shows base colours, not textures (umbrella Known Limitation 4, diffuse half) | step 3, merge `7201ae3` |
| Race scale values are relative placeholders (`RACE_SCALE`; umbrella Known Limitation 3) | `e5c3601` (step 7 task 17: rooms from body height H) |
| Outdoor terrain is just ground: no cliffs, boulders or vegetation | step 1 (cliffs, water, lava), step 2 (trees, merge `b2913d2`), step 10 (Sites) |
| Water and mixed zones: outdoor + water; a cave mouth in a hillside | step 1 (water plane, `AWT`); step 5 (outdoor dungeon) |
| Cave ceilings drop with the cave size shift | step 22 (decision 41 A3: footprints, not heights) |
| A cave District in another theme's zone gets no cave decor; after a built District it gets built walls | step 22 (District looks) |
| Warm light, wall torches and treasure dressing in cave builds | step 22 (decision 41 A2) |
| A flooded room's water is a square in its middle | step 24 |
| Wind the whole route, not each leg; cave rooms twice as far apart | step 25 (run factor 4) |
| A windiness scalar | step 26 |
| Rooms opening straight into each other (stock 0.30 of edges) | step 29 |
| Corridor lights: no corridor RoomContexts | `c498ef0` (step 12 task 14) |
| The tomb layer does nothing outside a tomb | step 15 decision 5 (struck in its archive) |
| Natural geometry style (M5 `natural.py`) | superseded by step 8's `rough` style (decision 28) |
| Light-density stat reads 0 in profiles | not a bug (stock lights by MOD placement); kept as a note in DESIGN |
