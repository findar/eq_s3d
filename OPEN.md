# Open items

Every known open item in one list, rolled up from the pillars' `OPEN.md` files under
[`docs/pillars/`](docs/pillars/README.md), where each item has its full text and how it was
checked. Built at master `c3d9b99` (2026-11-27) from every step spec's `archive.md`
"Follow-ups", ROADMAP's "Carried from step N" lists, "Known issues" and "Design work captured",
the umbrella spec's Known Limitations, and the gaps found on 2026-11-27. Duplicates were merged;
each item was checked against the code, and the ones already fixed are listed at the end with
their commit.

**Status**: **open** (to do), **parked** (known, deliberately left), **waiting** (on the user's
word or eyes), **in flight** (an active step covers it).

## Summary

| Pillar | Open | In flight | Parked | Waiting | Total | Already fixed |
|---|---|---|---|---|---|---|
| [P-A Web app and controls](docs/pillars/P-A-web-app/OPEN.md) | 12 | 0 | 4 | 1 | 17 | 3 |
| [P-B Traversable](docs/pillars/P-B-traversable/OPEN.md) | 10 | 2 | 1 | 1 | 14 | 6 |
| [P-C Usable in RoF2 and EQEmu](docs/pillars/P-C-rof2-eqemu/OPEN.md) | 4 | 0 | 1 | 7 | 12 | 3 |
| [P-D True-layout artifacts](docs/pillars/P-D-true-layout/OPEN.md) | 3 | 1 | 0 | 1 | 5 | 3 |
| [P-E EverQuest look and feel](docs/pillars/P-E-look-and-feel/OPEN.md) | 29 | 0 | 3 | 5 | 37 | 15 |
| [P-F Iterative feedback](docs/pillars/P-F-iterative-feedback/OPEN.md) | 6 | 0 | 0 | 1 | 7 | 4 |
| [P-G Engaging every time](docs/pillars/P-G-engaging/OPEN.md) | 27 | 1 | 2 | 7 | 37 | 10 |
| [P-H World](docs/pillars/P-H-world/OPEN.md) | 3 | 0 | 0 | 1 | 4 | 1 |
| [Engineering](docs/pillars/ENG-engineering/OPEN.md) | 9 | 5 | 2 | 0 | 16 | 3 |
| **All** | **103** | **9** | **13** | **24** | **149** | **48** |

## Waiting on the user

These need a decision or a look; nothing else unblocks them.

| ID | Item | Pillar |
|---|---|---|
| C-1 | Load an exported zone in the RoF2 client and apply its SQL on an EQEmu server (never done) | P-C |
| C-2, C-3, C-10 | In the client: door swing, object rotation direction, a hand-renamed export | P-C |
| C-7 | Spawns: should the tool populate a zone at all? | P-C |
| C-8 | Client art in exports: how to treat a build that packs models from the user's install | P-C |
| C-9 | `.s3d` era output: wanted? | P-C |
| D-5 | The in-client map window (follows C-1) | P-D |
| A-15 | Decision 19's content renames (`purpose`, `builder`, `inhabitants`, `element`, `condition`): still wanted? | P-A |
| G-1 | Requirement 22, topology control: still wanted, given Graph rule sets? | P-G |
| G-2 | Districts on by default for 8+ rooms? | P-G |
| G-3 | Wilderness size from a stock range? | P-G |
| H-1 | The multi-zone world design review | P-H |
| B-11 | The M1 human acceptance walk (task 22.5) | P-B |
| F-4, L-1 … L-9 | Looks not taken (below) | P-E, P-F, P-G |

## The gaps found on 2026-11-27

| Gap | Item |
|---|---|
| No in-client proof | C-1 (and C-2, C-3, D-5) |
| EQEmu server map, water and nav files | C-6 |
| Authoring hand-off | the manual finishing pass has no export to an editor and no guide beyond the sidecar; folded into X-1 (user docs) and C-11 (door models) |
| Spawns | C-7 |
| Client performance | C-12 |
| `.s3d` era | C-9 |
| Client art in exports | C-8 |
| CI, releases, migrations, user docs | X-1 |
| Failure dashboard | X-2 |

## Every open item

### P-A Web app and controls

| ID | Item | Status | Source |
|---|---|---|---|
| A-1 | Stale-code banner covers the Controls, can't be dismissed, fires on docs-only merges | open | ROADMAP Known issues |
| A-2 | Open Controls cover the top of the 3D view | open | step 14 |
| A-3 | Hidden controls still sent (sidecar records them) | parked | step 14 |
| A-4 | Rule set, Theme and Race lists hard-coded in `web/index.html` | open | step 6 |
| A-5 | Decor tooltip says "in the rooms" | open | step 11 |
| A-6 | Control values set by script don't reach the page's state | open | step 17 |
| A-7 | WASD while the Hall length slider has focus: unchecked | open | step 30 |
| A-8 | CLI has no theme, race, tint, winding or hall-length flags | open | step 6; found here |
| A-9 | Prompt words don't choose a layout or rule set | open | step 6 |
| A-10 | A race with no theme builds fortress rooms | open | step 6 |
| A-11 | Districts numbered 1 on the page, 0 in warnings; raw Purpose names | open | step 20 |
| A-12 | `tsc` errors; `@types/three` deferred | parked | step 17; ROADMAP |
| A-13 | `.js` served as `text/plain` via port 8000 on this machine | open | ROADMAP |
| A-14 | One ~570 kB web bundle chunk | parked | ROADMAP |
| A-15 | Decision 19's content renames never landed | waiting | found here |
| A-16 | Server doesn't auto-reload | parked | ROADMAP |
| A-17 | `test_cave_words_mean_dungeon` thorough failure ("cave outdoor dungeon") | open | step 19 |

### P-B Traversable

| ID | Item | Status | Source |
|---|---|---|---|
| B-1 | No headroom check over ordinary standable faces | open | umbrella KL 10 |
| B-2 | Seam rule joins floors with no wall test | open | step 31 |
| B-3 | A solid Feature's hollow reads as floor | open | step 29 |
| B-4 | Three gate residuals (footprint cuts, seeds named) | open | steps 23, 26 |
| B-5 | cave classic dramatic 21 s1866540615 fails in a fresh process | open | steps 30, 31 |
| B-6 | Two `--pair` seeds fail on master | open | step 31 |
| B-7 | 16-room Graph seed 26 open seam with Decor none | open | step 11 |
| B-8 | Thorough-profile failures (`test_raw_navigable`, `test_room_placement` f4, the tent, the outline at 300 examples) | open | steps 15, 18–21, 28 |
| B-9 | Check the plan before the mesh | in flight (step 33) | step 30 |
| B-10 | Intersecting corridors on the elevated path (seed 105770060) | parked | M1 |
| B-11 | M1 human acceptance walk (22.5) | waiting | M1 |
| B-12 | Elevation on drops the semantic sink/raise | open | ROADMAP Known issues |
| B-13 | `corridor_conflicts` measures the straight route, not the path | open | step 25 |
| B-14 | Loops-first planning; corridors as placed blocks | in flight (step 33) | step 33 |

### P-C Usable in RoF2 and EQEmu

| ID | Item | Status | Source |
|---|---|---|---|
| C-1 | No in-client load, no SQL applied on a server | waiting | step 17; gap |
| C-2 | Door swing and hinge unchecked in the client | waiting | step 17 |
| C-3 | `.eqg` rotation direction unchecked in the client | waiting | step 11 |
| C-4 | Zone row sets only safe point and `underworld`; no `ztype`/sky mapping | open | step 17; decision 19 |
| C-5 | Key items are placeholders | parked | step 17 |
| C-6 | No EQEmu server map, water map or navmesh | open | gap |
| C-7 | No spawns | waiting | gap |
| C-8 | Client art packed into exports | waiting | gap |
| C-9 | No `.s3d` output | waiting | gap |
| C-10 | Hand-renamed export: does it load? | waiting | decision 15 |
| C-11 | Door model catalogue (every door is `BBDOOR1`) | open | ROADMAP design item |
| C-12 | Client performance not measured | open | gap |

### P-D True-layout artifacts

| ID | Item | Status | Source |
|---|---|---|---|
| D-1 | Map return marks inferred | in flight (step 32 task 3) | step 31 |
| D-2 | District hulls overlap; a label under the legend | open | steps 20, 31 |
| D-3 | A failed outline trace gets no layers | open | step 31 |
| D-4 | Extra depth band at seed 403 | open | step 13 |
| D-5 | In-client map window unproven | waiting | decision 21c |

### P-E EverQuest look and feel

| ID | Item | Status | Source |
|---|---|---|---|
| E-1 | Normal maps (Req 16) and the preview's normal half | parked | step 4 |
| E-2 | ConformanceReport (Req 15) never built | open | umbrella |
| E-3 | Wilderness ground, water and tree textures | open | step 4 |
| E-4 | Stairs: two shapes, all alike, square in caves | open | user 2026-11-22; steps 8, 9 |
| E-5 | Lava rooms: raised box, no pit, no source | open | user 2026-11-22 |
| E-6 | Every wilderness gets a lava patch | open | user 2026-11-22 |
| E-7 | Classic-layout caves keep box walls | open | step 21 |
| E-8 | Built corridors, stairs and Bridges axis-aligned | open | M1; decision 42 |
| E-9 | Warrens and short, Z and U corridors barely wind | open | steps 25, 26 |
| E-10 | Seam lines at the hewn doorway | open | step 26 |
| E-11 | No water in an outdoor cave's flooded galleries | open | step 21 |
| E-12 | Water a flat colour in the preview | open | step 24 |
| E-13 | Shoreline below water; 150 u vs 160 u frame drift | open | ROADMAP |
| E-14 | One biome only (plains) | open | step 13 |
| E-15 | City style profile thin (6 zones) | open | ROADMAP |
| E-16 | Cave corridors dark; no decor in winding tunnels | open | steps 22, 23 |
| E-17 | Sparse cave Districts | open | step 22 |
| E-18 | A cave District drawing mostly `hewn` | open | step 22 |
| E-19 | VSPBLOCK301 tagged rock | open | step 21 |
| E-20 | Assemblies placed whole | open | step 11 |
| E-21 | Wall Props into walls; +X front assumed | open | step 11 |
| E-22 | GENMETCRATE700 twice stock size | open | step 11 |
| E-23 | City decor near band tops; city seed 53 | open | steps 11, 12 |
| E-24 | Later-era models; generated Props | open | step 11 |
| E-25 | Decor survey reads the tallest room as open sky | open | step 27 |
| E-26 | Stair and Bridge corridors get no decor | open | step 12 |
| E-27 | Dais fallback looser than the gate | open | step 26 |
| E-28 | `stage.py decor_stage` doesn't `settle_room` | open | step 15 |
| E-29 | `decor_room.py` ignores Districts | open | step 22 |
| E-30 | Sites not in the room view | open | step 15 |
| E-31 | Room view's slow first call | parked | step 15 |
| E-32 | Boulders as short pillars; sunken court; flared columns | parked | step 9 |
| L-4 | Look: water's edge at a doorway | waiting | step 24 |
| L-5 | Look: step 25 task 5's boss and dais fixes | waiting | step 25 |
| L-6 | Look: step 26 task 10's Bridges, dais decor, stalactite | waiting | step 26 |
| L-8 | Look: step 29 cave clumps | waiting | step 29 |
| L-9 | Look: step 21 caves (acceptance skipped) | waiting | step 21 |

### P-F Iterative feedback

| ID | Item | Status | Source |
|---|---|---|---|
| F-1 | Six edit ops answer "not yet supported" | open | step 18 |
| F-2 | A `rooms_seed` rebuild drops an edited version's edits | open | step 18 |
| F-3 | Edit tint a disc on classic/city; corridors untinted | open | step 18 |
| F-4 | Look: step 18's resizes, tint, "the boss room" | waiting | step 18 |
| F-5 | Stale District `room_ids` after removing rooms (latent) | open | step 20 |
| F-6 | A contents seed for Structure and Clutter | open | steps 9, 11, 12 |
| F-7 | Editing rule recipes from the page or a prompt | open | step 6 |

### P-G Engaging every time

| ID | Item | Status | Source |
|---|---|---|---|
| G-1 | Requirement 22, topology control, never built | waiting | umbrella |
| G-2 | Districts default-on for 8+ rooms? | waiting | step 20 |
| G-3 | Wilderness size | waiting | step 10 |
| G-4 | Other ways into an outdoor dungeon; a wider Mouth | open | user 2026-11-22 |
| G-5 | One-way walls via doors | open | umbrella scope table |
| G-6 | Breach pairs at 2+ links down to 68% | in flight (step 32 task 1) | step 31 |
| G-7 | An intrusion with no breach on Dramatic | open | step 31 |
| G-8 | Short drops into the goblins | open | step 31 |
| G-9 | Classic breaches have no rough form | open | step 31 |
| G-10 | A third District breached too | open | step 31 |
| G-11 | Similar light across some Thresholds | open | step 20 |
| G-12 | Repeated Purpose alternates; `ruined` never appears | open | step 20 |
| G-13 | Second cave District has no crystal grotto boss | open | step 22 |
| G-14 | `layout.rooms.<id>.district` reads 0 | open | step 22 |
| G-15 | Low stacking room type | open | steps 7, 8, 9 |
| G-16 | Cities share dungeon geometry; no city room types | open | steps 7, 11 |
| G-17 | Dragon stairs very long | open | step 7 |
| G-18 | Dramatic barely more than Moderate | open | step 7 |
| G-19 | Outdoor dungeons rarely reach three Levels | open | step 7 |
| G-20 | Giant and dragon outdoor dungeons drop rooms | open | steps 5, 7 |
| G-21 | Height bands overlap at the top | parked | step 7 |
| G-22 | Rule-format gaps (wildcard kind, reattach side, budgets) | open | step 6 |
| G-23 | Warren bands rest on one stock zone | open | step 6 |
| G-24 | Outdoor loop corridors lost to bigger rooms | open | step 27 |
| G-25 | Fit `dungeon_keep_clear` to the rooms | open | step 27 |
| G-26 | Fortress's bigger median room; an outdoor dungeon's lost stair | open | step 27 |
| G-27 | Cave stairs, flat quality fails 5.0%, entrance clump in a row | open | step 29 |
| G-28 | Outdoor halls stop at ~1.6× | parked | step 30 |
| G-29 | Site weights vs a stock kind survey | open | step 13 |
| G-30 | Outdoor-dungeon points favour small recipes | open | step 13 |
| G-31 | Dense gathers less than Normal | open | step 13 |
| G-32 | Farmsteads lose their barn; the survey splits farmsteads | open | steps 10, 13 |
| G-33 | `altar_stone` built, never placed | open | step 10 |
| L-1 | Look: the quality banner | waiting | step 19 |
| L-2 | Look: palette and light across a Threshold | waiting | step 20 |
| L-3 | Look: step 22 District looks | waiting | step 22 |
| L-7 | Look: step 27's angled openings and tunnels | waiting | step 27 |

### P-H World

| ID | Item | Status | Source |
|---|---|---|---|
| H-1 | Multi-zone worlds and zone lines | waiting | ROADMAP; step 12 |
| H-2 | The `door` Socket kind is reserved, never made | open | step 12 |
| H-3 | An exact Mouth Socket; several dungeons per World | open | step 12 |
| H-4 | Outdoor-dungeon helpers still re-derive the landscape | open | step 12 |

### Engineering

| ID | Item | Status | Source |
|---|---|---|---|
| X-1 | No CI, releases, migrations or user docs | open | gap |
| X-2 | No failure dashboard | open | gap |
| X-3 | Heavy-run lock across agents | in flight (project-docs task 5) | project-docs |
| X-4 | Build time outside the gate | in flight (step 33) | step 28 |
| X-5 | Split the 271 s corridor-clearance sweep test | open | steps 12, 28 |
| X-6 | Stale "no `slow` marker" comments | open | step 28 |
| X-7 | Cave draw time outside `embed.py` | open | steps 27, 29 |
| X-8 | Slow outdoor-dungeon Draws (223 s worst) | in flight (step 33) | step 19 |
| X-9 | Rough 30-room builds ~32 s: re-measure | open | step 8 |
| X-10 | A parallel run that once hung | parked | ROADMAP |
| X-11 | Shared Python env drifts from the pins | open | ROADMAP |
| X-12 | PFS footer timestamp | parked | ROADMAP |
| X-13 | Inspector has no side-elevation view | open | ROADMAP |
| X-14 | Umbrella Requirement 33 cited but never written | open | found here |
| X-15 | Umbrella design and steering describe modules and behaviour the code doesn't have | in flight (project-docs) | found here |
| X-16 | Docs organised by history | in flight (project-docs) | project-docs |

## Already fixed (dropped)

48 items recorded as open somewhere turned out to be fixed or superseded. Each pillar's
`OPEN.md` lists its own under "Fixed"; the ones with a single fixing commit:

| Item | Fixed by | Pillar |
|---|---|---|
| `ZONE_PLAN_JSON_SCHEMA` lacks `winding`, `hall_length` | `2e325f3` | P-A |
| Walk surface takes ceilings as floor | `e25abe6` | P-B |
| Step 23 residuals: outline slit; decor clear width | `7566697`, `74ae74e` | P-B |
| Map outline depends on face order | `0af5124` | P-D |
| Socket markers infer the map frame | `bd394c6` | P-D |
| Race scale placeholders (`RACE_SCALE`) | `e5c3601` | P-E |
| No corridor RoomContexts (corridor lights) | `c498ef0` | P-E |
| `edit_outside_bands` waits on quality bands | `7466fef` | P-F |
| `keep_clear_shapes` duplicates `entrance_keep_clear` | `570ff4f` | P-G |
| Same seed, different build in one process | `6781622` | P-G, ENG |

The rest were closed by whole steps (for example multi-level dungeons by step 7, the district
look by step 22, the flooded-room square by step 24, the rest of M4 by step 18, the SQL export by
step 17) and are listed with their step in the pillar files.
