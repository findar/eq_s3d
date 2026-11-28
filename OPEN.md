# Open items

Every known open item in one list, rolled up from the pillars' `OPEN.md` files under
[`docs/pillars/`](docs/pillars/README.md). Each pillar file has the item's full text and says how
it was checked. Each ID below links to that row.

The list was built at master `c3d9b99` (2026-11-27, the commit that opened the project-docs
spec) from these sources:

- every step spec's `archive.md` "Follow-ups";
- in [ROADMAP](ROADMAP.md): the "Carried from step N" lists in "Pick up here", "Known issues" and "Design work
  captured";
- the umbrella design's [Known Limitations](.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them);
- the gaps found on 2026-11-27, listed in [project-docs requirement 3](.kiro/specs/project-docs/requirements.md#requirements).

Duplicates were merged. Each item was checked against the code; the ones already fixed are
listed at the end with their commit.

IDs are `P-<n>-<k>`: pillar number, then item number ([`docs/STYLE.md`](docs/STYLE.md)).
**Status**: **open** (to do), **parked** (known, deliberately left), **waiting** (on the user's
word or eyes), **in flight** (an active step covers it). **Source**: where the item was first
recorded; "step N archive" is that step's `archive.md` "Follow-ups".

## Summary

| Pillar | Open | In flight | Parked | Waiting | Total | Already fixed |
|---|---|---|---|---|---|---|
| [P-1 Web app and controls](docs/pillars/P-1-web-app/OPEN.md) | 12 | 0 | 4 | 1 | 17 | 3 |
| [P-2 Traversable](docs/pillars/P-2-traversable/OPEN.md) | 10 | 2 | 1 | 1 | 14 | 6 |
| [P-3 Usable in RoF2 and EQEmu](docs/pillars/P-3-rof2-eqemu/OPEN.md) | 4 | 0 | 1 | 7 | 12 | 3 |
| [P-4 True-layout artifacts](docs/pillars/P-4-true-layout/OPEN.md) | 3 | 1 | 0 | 1 | 5 | 3 |
| [P-5 EverQuest look and feel](docs/pillars/P-5-look-and-feel/OPEN.md) | 29 | 0 | 3 | 5 | 37 | 15 |
| [P-6 Iterative feedback](docs/pillars/P-6-iterative-feedback/OPEN.md) | 7 | 0 | 0 | 1 | 8 | 4 |
| [P-7 Engaging every time](docs/pillars/P-7-engaging/OPEN.md) | 27 | 1 | 2 | 7 | 37 | 10 |
| [P-8 World](docs/pillars/P-8-world/OPEN.md) | 3 | 0 | 0 | 1 | 4 | 1 |
| [P-9 Engineering](docs/pillars/P-9-engineering/OPEN.md) | 9 | 5 | 2 | 0 | 16 | 3 |
| **All** | **104** | **9** | **13** | **24** | **150** | **48** |

## Waiting on the user

These need a decision or a look; nothing else unblocks them.

| ID | Item | Pillar |
|---|---|---|
| [P-3-1](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-1) | Load an exported zone in the RoF2 client and apply its SQL on an EQEmu server (never done) | P-3 |
| [P-3-2](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-2), [P-3-3](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-3), [P-3-10](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-10) | In the client: door swing, object rotation direction, a hand-renamed export | P-3 |
| [P-3-7](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-7) | Spawns: should the tool populate a zone at all? | P-3 |
| [P-3-8](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-8) | Client art in exports: how to treat a build that packs models from the user's install | P-3 |
| [P-3-9](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-9) | `.s3d` era output: wanted? | P-3 |
| [P-4-5](docs/pillars/P-4-true-layout/OPEN.md#p-4-5) | The in-client map window (follows [P-3-1](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-1)) | P-4 |
| [P-1-15](docs/pillars/P-1-web-app/OPEN.md#p-1-15) | [Umbrella decision 19](.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)'s content renames (`purpose`, `builder`, `inhabitants`, `element`, `condition`): still wanted? | P-1 |
| [P-7-1](docs/pillars/P-7-engaging/OPEN.md#p-7-1) | Topology control ([P-7-Req-2](docs/pillars/P-7-engaging/PLAN.md#p-7-req-2)): still wanted, given Graph rule sets? | P-7 |
| [P-7-2](docs/pillars/P-7-engaging/OPEN.md#p-7-2) | Districts on by default for 8+ rooms? | P-7 |
| [P-7-3](docs/pillars/P-7-engaging/OPEN.md#p-7-3) | Wilderness size from a stock range? | P-7 |
| [P-8-1](docs/pillars/P-8-world/OPEN.md#p-8-1) | The multi-zone world design review | P-8 |
| [P-2-11](docs/pillars/P-2-traversable/OPEN.md#p-2-11) | The [M1](.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) human acceptance walk (M1 task 22.5) | P-2 |
| [P-5-33](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-33) to [P-5-37](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-37), [P-6-4](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-4), [P-7-34](docs/pillars/P-7-engaging/OPEN.md#p-7-34) to [P-7-37](docs/pillars/P-7-engaging/OPEN.md#p-7-37) | Looks not taken: steps whose result nobody has looked at in 3D (listed below) | P-5, P-6, P-7 |

## The gaps found on 2026-11-27

| Gap | Item |
|---|---|
| No in-client proof | [P-3-1](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-1) (and [P-3-2](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-2), [P-3-3](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-3), [P-4-5](docs/pillars/P-4-true-layout/OPEN.md#p-4-5)) |
| EQEmu server map, water and nav files | [P-3-6](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-6) |
| Authoring hand-off | [P-6-8](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-8): the manual finishing pass has no export to an editing tool and no guide beyond the sidecar |
| Spawns | [P-3-7](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-7) |
| Client performance | [P-3-12](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-12) |
| `.s3d` era | [P-3-9](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-9) |
| Client art in exports | [P-3-8](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-8) |
| CI, releases, migrations, user docs | [P-9-1](docs/pillars/P-9-engineering/OPEN.md#p-9-1) |
| Failure dashboard | [P-9-2](docs/pillars/P-9-engineering/OPEN.md#p-9-2) |

## Every open item

### P-1 Web app and controls

| ID | Item | Status | Source |
|---|---|---|---|
| [P-1-1](docs/pillars/P-1-web-app/OPEN.md#p-1-1) | Stale-code banner covers the Controls, can't be dismissed, fires on docs-only merges | open | [ROADMAP "Known issues"](ROADMAP.md#known-issues--smaller-fixes) |
| [P-1-2](docs/pillars/P-1-web-app/OPEN.md#p-1-2) | Open Controls cover the top of the 3D view | open | [step 14 archive](.kiro/specs/zone-generator-web-cleanup/archive.md) |
| [P-1-3](docs/pillars/P-1-web-app/OPEN.md#p-1-3) | Hidden controls still sent (sidecar records them) | parked | [step 14 archive](.kiro/specs/zone-generator-web-cleanup/archive.md) |
| [P-1-4](docs/pillars/P-1-web-app/OPEN.md#p-1-4) | Rule set, Theme and Race lists hard-coded in [`web/index.html`](web/index.html) | open | [step 6 archive](.kiro/specs/zone-generator-graph-layout/archive.md) |
| [P-1-5](docs/pillars/P-1-web-app/OPEN.md#p-1-5) | Decor tooltip says "in the rooms" | open | [step 11 archive](.kiro/specs/zone-generator-room-decor/archive.md) |
| [P-1-6](docs/pillars/P-1-web-app/OPEN.md#p-1-6) | Control values set by script don't reach the page's state | open | [step 17 archive](.kiro/specs/zone-generator-export/archive.md) |
| [P-1-7](docs/pillars/P-1-web-app/OPEN.md#p-1-7) | WASD while the Hall length slider has focus: unchecked | open | [step 30 archive](.kiro/specs/zone-generator-hall-length/archive.md) |
| [P-1-8](docs/pillars/P-1-web-app/OPEN.md#p-1-8) | CLI has no theme, race, tint, winding or hall-length flags | open | [step 6 archive](.kiro/specs/zone-generator-graph-layout/archive.md); found by [project-docs task 1](.kiro/specs/project-docs/cards/01-proposal.md) |
| [P-1-9](docs/pillars/P-1-web-app/OPEN.md#p-1-9) | Prompt words don't choose a layout or rule set | open | [step 6 archive](.kiro/specs/zone-generator-graph-layout/archive.md) |
| [P-1-10](docs/pillars/P-1-web-app/OPEN.md#p-1-10) | A race with no theme builds fortress rooms | open | [step 6 archive](.kiro/specs/zone-generator-graph-layout/archive.md) |
| [P-1-11](docs/pillars/P-1-web-app/OPEN.md#p-1-11) | Districts numbered 1 on the page, 0 in warnings; raw Purpose names | open | [step 20 archive](.kiro/specs/zone-generator-districts/archive.md) |
| [P-1-12](docs/pillars/P-1-web-app/OPEN.md#p-1-12) | `tsc` errors; `@types/three` deferred | parked | [step 17 archive](.kiro/specs/zone-generator-export/archive.md); [ROADMAP](ROADMAP.md) |
| [P-1-13](docs/pillars/P-1-web-app/OPEN.md#p-1-13) | `.js` served as `text/plain` via port 8000 on this machine | open | [ROADMAP](ROADMAP.md) |
| [P-1-14](docs/pillars/P-1-web-app/OPEN.md#p-1-14) | One ~570 kB web bundle chunk | parked | [ROADMAP](ROADMAP.md) |
| [P-1-15](docs/pillars/P-1-web-app/OPEN.md#p-1-15) | [Umbrella decision 19](.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)'s content renames never landed | waiting | found by [project-docs task 1](.kiro/specs/project-docs/cards/01-proposal.md) |
| [P-1-16](docs/pillars/P-1-web-app/OPEN.md#p-1-16) | Server doesn't auto-reload | parked | [ROADMAP](ROADMAP.md) |
| [P-1-17](docs/pillars/P-1-web-app/OPEN.md#p-1-17) | `test_cave_words_mean_dungeon` thorough failure ("cave outdoor dungeon") | open | [step 19 archive](.kiro/specs/zone-generator-quality/archive.md) |

### P-2 Traversable

| ID | Item | Status | Source |
|---|---|---|---|
| [P-2-1](docs/pillars/P-2-traversable/OPEN.md#p-2-1) | No headroom check over ordinary standable faces | open | [umbrella Known Limitation 10](.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them) |
| [P-2-2](docs/pillars/P-2-traversable/OPEN.md#p-2-2) | Seam rule joins floors with no wall test | open | [step 31 archive](.kiro/specs/zone-generator-district-races/archive.md) |
| [P-2-3](docs/pillars/P-2-traversable/OPEN.md#p-2-3) | A solid Feature's hollow reads as floor | open | [step 29 archive](.kiro/specs/zone-generator-cave-clumps/archive.md) |
| [P-2-4](docs/pillars/P-2-traversable/OPEN.md#p-2-4) | Three gate residuals (footprint cuts, seeds named) | open | steps [23](.kiro/specs/zone-generator-winding-tunnels/archive.md) and [26](.kiro/specs/zone-generator-winding-control/archive.md) archives |
| [P-2-5](docs/pillars/P-2-traversable/OPEN.md#p-2-5) | cave classic dramatic 21 s1866540615 fails in a fresh process | open | steps [30](.kiro/specs/zone-generator-hall-length/archive.md) and [31](.kiro/specs/zone-generator-district-races/archive.md) archives |
| [P-2-6](docs/pillars/P-2-traversable/OPEN.md#p-2-6) | Two `--pair` seeds fail on master | open | [step 31 archive](.kiro/specs/zone-generator-district-races/archive.md) |
| [P-2-7](docs/pillars/P-2-traversable/OPEN.md#p-2-7) | 16-room Graph seed 26 open seam with Decor none | open | [step 11 archive](.kiro/specs/zone-generator-room-decor/archive.md) |
| [P-2-8](docs/pillars/P-2-traversable/OPEN.md#p-2-8) | Thorough-profile failures (`test_raw_navigable`, `test_room_placement` f4, the tent, the outline at 300 examples) | open | steps [15](.kiro/specs/zone-generator-decor-rules/archive.md), [18](.kiro/specs/zone-generator-edits/archive.md)–[21](.kiro/specs/zone-generator-cave/archive.md) and [28](.kiro/specs/test-speed/archive.md) archives |
| [P-2-9](docs/pillars/P-2-traversable/OPEN.md#p-2-9) | Check the plan before the mesh | in flight ([step 33](.kiro/specs/zone-generator-layout-repair/tasks.md)) | [step 30 archive](.kiro/specs/zone-generator-hall-length/archive.md) |
| [P-2-10](docs/pillars/P-2-traversable/OPEN.md#p-2-10) | Intersecting corridors on the elevated path (seed 105770060) | parked | [M1](.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) |
| [P-2-11](docs/pillars/P-2-traversable/OPEN.md#p-2-11) | [M1](.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) human acceptance walk (22.5) | waiting | M1 |
| [P-2-12](docs/pillars/P-2-traversable/OPEN.md#p-2-12) | Elevation on drops the semantic sink/raise | open | [ROADMAP "Known issues"](ROADMAP.md#known-issues--smaller-fixes) |
| [P-2-13](docs/pillars/P-2-traversable/OPEN.md#p-2-13) | `corridor_conflicts` measures the straight route, not the path | open | [step 25 archive](.kiro/specs/zone-generator-winding-routes/archive.md) |
| [P-2-14](docs/pillars/P-2-traversable/OPEN.md#p-2-14) | Loops-first planning; corridors as placed blocks | in flight ([step 33](.kiro/specs/zone-generator-layout-repair/tasks.md)) | [step 33 archive](.kiro/specs/zone-generator-layout-repair/archive.md) |

### P-3 Usable in RoF2 and EQEmu

| ID | Item | Status | Source |
|---|---|---|---|
| [P-3-1](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-1) | No in-client load, no SQL applied on a server | waiting | [step 17 archive](.kiro/specs/zone-generator-export/archive.md); gap 2026-11-27 |
| [P-3-2](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-2) | Door swing and hinge unchecked in the client | waiting | [step 17 archive](.kiro/specs/zone-generator-export/archive.md) |
| [P-3-3](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-3) | `.eqg` rotation direction unchecked in the client | waiting | [step 11 archive](.kiro/specs/zone-generator-room-decor/archive.md) |
| [P-3-4](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-4) | Zone row sets only safe point and `underworld`; no `ztype`/sky mapping | open | [step 17 archive](.kiro/specs/zone-generator-export/archive.md); [umbrella decision 19](.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) |
| [P-3-5](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-5) | Key items are placeholders | parked | [step 17 archive](.kiro/specs/zone-generator-export/archive.md) |
| [P-3-6](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-6) | No EQEmu server map, water map or navmesh | open | gap 2026-11-27 |
| [P-3-7](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-7) | No spawns | waiting | gap 2026-11-27 |
| [P-3-8](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-8) | Client art packed into exports | waiting | gap 2026-11-27 |
| [P-3-9](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-9) | No `.s3d` output | waiting | gap 2026-11-27 |
| [P-3-10](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-10) | Hand-renamed export: does it load? | waiting | [umbrella decision 15](.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) |
| [P-3-11](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-11) | Door model catalogue (every door is `BBDOOR1`) | open | [ROADMAP "Design work captured"](ROADMAP.md#design-work-captured-not-yet-built) |
| [P-3-12](docs/pillars/P-3-rof2-eqemu/OPEN.md#p-3-12) | Client performance not measured | open | gap 2026-11-27 |

### P-4 True-layout artifacts

| ID | Item | Status | Source |
|---|---|---|---|
| [P-4-1](docs/pillars/P-4-true-layout/OPEN.md#p-4-1) | Map return marks inferred | in flight ([step 32](.kiro/specs/zone-generator-races-followups/tasks.md) task 3) | [step 31 archive](.kiro/specs/zone-generator-district-races/archive.md) |
| [P-4-2](docs/pillars/P-4-true-layout/OPEN.md#p-4-2) | District hulls overlap; a label under the legend | open | steps [20](.kiro/specs/zone-generator-districts/archive.md) and [31](.kiro/specs/zone-generator-district-races/archive.md) archives |
| [P-4-3](docs/pillars/P-4-true-layout/OPEN.md#p-4-3) | A failed outline trace gets no layers | open | [step 31 archive](.kiro/specs/zone-generator-district-races/archive.md) |
| [P-4-4](docs/pillars/P-4-true-layout/OPEN.md#p-4-4) | Extra depth band at seed 403 | open | [step 13 archive](.kiro/specs/zone-generator-site-sockets/archive.md) |
| [P-4-5](docs/pillars/P-4-true-layout/OPEN.md#p-4-5) | In-client map window unproven | waiting | [umbrella decision 21](.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part c |

### P-5 EverQuest look and feel

| ID | Item | Status | Source |
|---|---|---|---|
| [P-5-1](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-1) | Normal maps ([ZG-Req-16](.kiro/specs/zone-generator/requirements.md#requirement-16-procedural-normal-maps)) and the preview's normal half | parked | [step 4 archive](.kiro/specs/zone-generator-interesting-textures/archive.md) |
| [P-5-2](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-2) | The conformance report ([ZG-Req-15](.kiro/specs/zone-generator/requirements.md#requirement-15-era-fidelity-and-measured-conformance)) never built | open | umbrella spec |
| [P-5-3](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-3) | Wilderness ground, water and tree textures | open | [step 4 archive](.kiro/specs/zone-generator-interesting-textures/archive.md) |
| [P-5-4](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-4) | Stairs: two shapes, all alike, square in caves | open | the user, 2026-11-22, in [ROADMAP "Known issues"](ROADMAP.md#known-issues--smaller-fixes); steps [8](.kiro/specs/zone-generator-room-walls/archive.md) and [9](.kiro/specs/zone-generator-room-layouts/archive.md) archives |
| [P-5-5](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-5) | Lava rooms: raised box, no pit, no source | open | the user, 2026-11-22, in [ROADMAP "Known issues"](ROADMAP.md#known-issues--smaller-fixes) |
| [P-5-6](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-6) | Every wilderness gets a lava patch | open | the user, 2026-11-22, in [ROADMAP "Known issues"](ROADMAP.md#known-issues--smaller-fixes) |
| [P-5-7](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-7) | Classic-layout caves keep box walls | open | [step 21 archive](.kiro/specs/zone-generator-cave/archive.md) |
| [P-5-8](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-8) | Built corridors, stairs and Bridges axis-aligned | open | [M1](.kiro/specs/zone-generator-m1-controls-traversability/tasks.md); [umbrella decision 42](.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) |
| [P-5-9](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-9) | Warrens and short, Z and U corridors barely wind | open | steps [25](.kiro/specs/zone-generator-winding-routes/archive.md) and [26](.kiro/specs/zone-generator-winding-control/archive.md) archives |
| [P-5-10](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-10) | Seam lines at the hewn doorway | open | [step 26 archive](.kiro/specs/zone-generator-winding-control/archive.md) |
| [P-5-11](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-11) | No water in an outdoor cave's flooded galleries | open | [step 21 archive](.kiro/specs/zone-generator-cave/archive.md) |
| [P-5-12](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-12) | Water a flat colour in the preview | open | [step 24 archive](.kiro/specs/zone-generator-flooded-rooms/archive.md) |
| [P-5-13](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-13) | Shoreline below water; 150 u vs 160 u frame drift | open | [ROADMAP](ROADMAP.md) |
| [P-5-14](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-14) | One biome only (plains) | open | [step 13 archive](.kiro/specs/zone-generator-site-sockets/archive.md) |
| [P-5-15](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-15) | City style profile thin (6 zones) | open | [ROADMAP](ROADMAP.md) |
| [P-5-16](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-16) | Cave corridors dark; no decor in winding tunnels | open | steps [22](.kiro/specs/zone-generator-district-looks/archive.md) and [23](.kiro/specs/zone-generator-winding-tunnels/archive.md) archives |
| [P-5-17](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-17) | Sparse cave Districts | open | [step 22 archive](.kiro/specs/zone-generator-district-looks/archive.md) |
| [P-5-18](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-18) | A cave District drawing mostly `hewn` | open | [step 22 archive](.kiro/specs/zone-generator-district-looks/archive.md) |
| [P-5-19](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-19) | VSPBLOCK301 tagged rock | open | [step 21 archive](.kiro/specs/zone-generator-cave/archive.md) |
| [P-5-20](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-20) | Assemblies placed whole | open | [step 11 archive](.kiro/specs/zone-generator-room-decor/archive.md) |
| [P-5-21](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-21) | Wall Props into walls; +X front assumed | open | [step 11 archive](.kiro/specs/zone-generator-room-decor/archive.md) |
| [P-5-22](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-22) | GENMETCRATE700 twice stock size | open | [step 11 archive](.kiro/specs/zone-generator-room-decor/archive.md) |
| [P-5-23](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-23) | City decor near band tops; city seed 53 | open | steps [11](.kiro/specs/zone-generator-room-decor/archive.md) and [12](.kiro/specs/zone-generator-world-sockets/archive.md) archives |
| [P-5-24](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-24) | Later-era models; generated Props | open | [step 11 archive](.kiro/specs/zone-generator-room-decor/archive.md) |
| [P-5-25](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-25) | Decor survey reads the tallest room as open sky | open | [step 27 archive](.kiro/specs/zone-generator-random-placement/archive.md) |
| [P-5-26](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-26) | Stair and Bridge corridors get no decor | open | [step 12 archive](.kiro/specs/zone-generator-world-sockets/archive.md) |
| [P-5-27](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-27) | Dais fallback looser than the gate | open | [step 26 archive](.kiro/specs/zone-generator-winding-control/archive.md) |
| [P-5-28](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-28) | `stage.py decor_stage` doesn't `settle_room` | open | [step 15 archive](.kiro/specs/zone-generator-decor-rules/archive.md) |
| [P-5-29](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-29) | [`decor_room.py`](scripts/decor_room.py) ignores Districts | open | [step 22 archive](.kiro/specs/zone-generator-district-looks/archive.md) |
| [P-5-30](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-30) | Sites not in the room view | open | [step 15 archive](.kiro/specs/zone-generator-decor-rules/archive.md) |
| [P-5-31](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-31) | Room view's slow first call | parked | [step 15 archive](.kiro/specs/zone-generator-decor-rules/archive.md) |
| [P-5-32](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-32) | Boulders as short pillars; sunken court; flared columns | parked | [step 9 archive](.kiro/specs/zone-generator-room-layouts/archive.md) |
| [P-5-33](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-33) | Look: water's edge at a doorway | waiting | [step 24 archive](.kiro/specs/zone-generator-flooded-rooms/archive.md) |
| [P-5-34](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-34) | Look: [step 25](.kiro/specs/zone-generator-winding-routes/tasks.md) task 5's boss and dais fixes | waiting | [step 25 archive](.kiro/specs/zone-generator-winding-routes/archive.md) |
| [P-5-35](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-35) | Look: [step 26](.kiro/specs/zone-generator-winding-control/tasks.md) task 10's Bridges, dais decor, stalactite | waiting | [step 26 archive](.kiro/specs/zone-generator-winding-control/archive.md) |
| [P-5-36](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-36) | Look: [step 29](.kiro/specs/zone-generator-cave-clumps/tasks.md) cave clumps | waiting | [step 29 archive](.kiro/specs/zone-generator-cave-clumps/archive.md) |
| [P-5-37](docs/pillars/P-5-look-and-feel/OPEN.md#p-5-37) | Look: [step 21](.kiro/specs/zone-generator-cave/tasks.md) caves (acceptance skipped) | waiting | [step 21 archive](.kiro/specs/zone-generator-cave/archive.md) |

### P-6 Iterative feedback

| ID | Item | Status | Source |
|---|---|---|---|
| [P-6-1](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-1) | Six edit ops answer "not yet supported" | open | [step 18 archive](.kiro/specs/zone-generator-edits/archive.md) |
| [P-6-2](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-2) | A `rooms_seed` rebuild drops an edited version's edits | open | [step 18 archive](.kiro/specs/zone-generator-edits/archive.md) |
| [P-6-3](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-3) | Edit tint a disc on classic/city; corridors untinted | open | [step 18 archive](.kiro/specs/zone-generator-edits/archive.md) |
| [P-6-4](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-4) | Look: [step 18](.kiro/specs/zone-generator-edits/tasks.md)'s resizes, tint, "the boss room" | waiting | [step 18 archive](.kiro/specs/zone-generator-edits/archive.md) |
| [P-6-5](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-5) | Stale District `room_ids` after removing rooms (latent) | open | [step 20 archive](.kiro/specs/zone-generator-districts/archive.md) |
| [P-6-6](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-6) | A contents seed for Structure and Clutter | open | steps [9](.kiro/specs/zone-generator-room-layouts/archive.md), [11](.kiro/specs/zone-generator-room-decor/archive.md) and [12](.kiro/specs/zone-generator-world-sockets/archive.md) archives |
| [P-6-7](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-7) | Editing rule recipes from the page or a prompt | open | [step 6 archive](.kiro/specs/zone-generator-graph-layout/archive.md) |
| [P-6-8](docs/pillars/P-6-iterative-feedback/OPEN.md#p-6-8) | The authoring hand-off: nothing supports the manual finishing pass | open | gap 2026-11-27 |

### P-7 Engaging every time

| ID | Item | Status | Source |
|---|---|---|---|
| [P-7-1](docs/pillars/P-7-engaging/OPEN.md#p-7-1) | Topology control ([P-7-Req-2](docs/pillars/P-7-engaging/PLAN.md#p-7-req-2)), never built | waiting | umbrella spec |
| [P-7-2](docs/pillars/P-7-engaging/OPEN.md#p-7-2) | Districts default-on for 8+ rooms? | waiting | [step 20 archive](.kiro/specs/zone-generator-districts/archive.md) |
| [P-7-3](docs/pillars/P-7-engaging/OPEN.md#p-7-3) | Wilderness size | waiting | [step 10 archive](.kiro/specs/zone-generator-wilderness-pois/archive.md) |
| [P-7-4](docs/pillars/P-7-engaging/OPEN.md#p-7-4) | Other ways into an outdoor dungeon; a wider Mouth | open | the user, 2026-11-22, in [ROADMAP "Known issues"](ROADMAP.md#known-issues--smaller-fixes) |
| [P-7-5](docs/pillars/P-7-engaging/OPEN.md#p-7-5) | One-way walls via doors | open | umbrella design "Scope of open task files" |
| [P-7-6](docs/pillars/P-7-engaging/OPEN.md#p-7-6) | Breach pairs at 2+ links down to 68% | in flight ([step 32](.kiro/specs/zone-generator-races-followups/tasks.md) task 1) | [step 31 archive](.kiro/specs/zone-generator-district-races/archive.md) |
| [P-7-7](docs/pillars/P-7-engaging/OPEN.md#p-7-7) | An intrusion with no breach on Dramatic | open | [step 31 archive](.kiro/specs/zone-generator-district-races/archive.md) |
| [P-7-8](docs/pillars/P-7-engaging/OPEN.md#p-7-8) | Short drops into the goblins | open | [step 31 archive](.kiro/specs/zone-generator-district-races/archive.md) |
| [P-7-9](docs/pillars/P-7-engaging/OPEN.md#p-7-9) | Classic breaches have no rough form | open | [step 31 archive](.kiro/specs/zone-generator-district-races/archive.md) |
| [P-7-10](docs/pillars/P-7-engaging/OPEN.md#p-7-10) | A third District breached too | open | [step 31 archive](.kiro/specs/zone-generator-district-races/archive.md) |
| [P-7-11](docs/pillars/P-7-engaging/OPEN.md#p-7-11) | Similar light across some Thresholds | open | [step 20 archive](.kiro/specs/zone-generator-districts/archive.md) |
| [P-7-12](docs/pillars/P-7-engaging/OPEN.md#p-7-12) | Repeated Purpose alternates; `ruined` never appears | open | [step 20 archive](.kiro/specs/zone-generator-districts/archive.md) |
| [P-7-13](docs/pillars/P-7-engaging/OPEN.md#p-7-13) | Second cave District has no crystal grotto boss | open | [step 22 archive](.kiro/specs/zone-generator-district-looks/archive.md) |
| [P-7-14](docs/pillars/P-7-engaging/OPEN.md#p-7-14) | `layout.rooms.<id>.district` reads 0 | open | [step 22 archive](.kiro/specs/zone-generator-district-looks/archive.md) |
| [P-7-15](docs/pillars/P-7-engaging/OPEN.md#p-7-15) | Low stacking room type | open | steps [7](.kiro/specs/zone-generator-dungeon-verticality/archive.md), [8](.kiro/specs/zone-generator-room-walls/archive.md) and [9](.kiro/specs/zone-generator-room-layouts/archive.md) archives |
| [P-7-16](docs/pillars/P-7-engaging/OPEN.md#p-7-16) | Cities share dungeon geometry; no city room types | open | steps [7](.kiro/specs/zone-generator-dungeon-verticality/archive.md) and [11](.kiro/specs/zone-generator-room-decor/archive.md) archives |
| [P-7-17](docs/pillars/P-7-engaging/OPEN.md#p-7-17) | Dragon stairs very long | open | [step 7 archive](.kiro/specs/zone-generator-dungeon-verticality/archive.md) |
| [P-7-18](docs/pillars/P-7-engaging/OPEN.md#p-7-18) | Dramatic barely more than Moderate | open | [step 7 archive](.kiro/specs/zone-generator-dungeon-verticality/archive.md) |
| [P-7-19](docs/pillars/P-7-engaging/OPEN.md#p-7-19) | Outdoor dungeons rarely reach three Levels | open | [step 7 archive](.kiro/specs/zone-generator-dungeon-verticality/archive.md) |
| [P-7-20](docs/pillars/P-7-engaging/OPEN.md#p-7-20) | Giant and dragon outdoor dungeons drop rooms | open | steps [5](.kiro/specs/zone-generator-outdoor-dungeon/archive.md) and [7](.kiro/specs/zone-generator-dungeon-verticality/archive.md) archives |
| [P-7-21](docs/pillars/P-7-engaging/OPEN.md#p-7-21) | Height bands overlap at the top | parked | [step 7 archive](.kiro/specs/zone-generator-dungeon-verticality/archive.md) |
| [P-7-22](docs/pillars/P-7-engaging/OPEN.md#p-7-22) | Rule-format gaps (wildcard kind, reattach side, budgets) | open | [step 6 archive](.kiro/specs/zone-generator-graph-layout/archive.md) |
| [P-7-23](docs/pillars/P-7-engaging/OPEN.md#p-7-23) | Warren bands rest on one stock zone | open | [step 6 archive](.kiro/specs/zone-generator-graph-layout/archive.md) |
| [P-7-24](docs/pillars/P-7-engaging/OPEN.md#p-7-24) | Outdoor loop corridors lost to bigger rooms | open | [step 27 archive](.kiro/specs/zone-generator-random-placement/archive.md) |
| [P-7-25](docs/pillars/P-7-engaging/OPEN.md#p-7-25) | Fit `dungeon_keep_clear` to the rooms | open | [step 27 archive](.kiro/specs/zone-generator-random-placement/archive.md) |
| [P-7-26](docs/pillars/P-7-engaging/OPEN.md#p-7-26) | Fortress's bigger median room; an outdoor dungeon's lost stair | open | [step 27 archive](.kiro/specs/zone-generator-random-placement/archive.md) |
| [P-7-27](docs/pillars/P-7-engaging/OPEN.md#p-7-27) | Cave stairs, flat quality fails 5.0%, entrance clump in a row | open | [step 29 archive](.kiro/specs/zone-generator-cave-clumps/archive.md) |
| [P-7-28](docs/pillars/P-7-engaging/OPEN.md#p-7-28) | Outdoor halls stop at ~1.6× | parked | [step 30 archive](.kiro/specs/zone-generator-hall-length/archive.md) |
| [P-7-29](docs/pillars/P-7-engaging/OPEN.md#p-7-29) | Site weights vs a stock kind survey | open | [step 13 archive](.kiro/specs/zone-generator-site-sockets/archive.md) |
| [P-7-30](docs/pillars/P-7-engaging/OPEN.md#p-7-30) | Outdoor-dungeon points favour small recipes | open | [step 13 archive](.kiro/specs/zone-generator-site-sockets/archive.md) |
| [P-7-31](docs/pillars/P-7-engaging/OPEN.md#p-7-31) | Dense gathers less than Normal | open | [step 13 archive](.kiro/specs/zone-generator-site-sockets/archive.md) |
| [P-7-32](docs/pillars/P-7-engaging/OPEN.md#p-7-32) | Farmsteads lose their barn; the survey splits farmsteads | open | steps [10](.kiro/specs/zone-generator-wilderness-pois/archive.md) and [13](.kiro/specs/zone-generator-site-sockets/archive.md) archives |
| [P-7-33](docs/pillars/P-7-engaging/OPEN.md#p-7-33) | `altar_stone` built, never placed | open | [step 10 archive](.kiro/specs/zone-generator-wilderness-pois/archive.md) |
| [P-7-34](docs/pillars/P-7-engaging/OPEN.md#p-7-34) | Look: the quality banner | waiting | [step 19 archive](.kiro/specs/zone-generator-quality/archive.md) |
| [P-7-35](docs/pillars/P-7-engaging/OPEN.md#p-7-35) | Look: palette and light across a Threshold | waiting | [step 20 archive](.kiro/specs/zone-generator-districts/archive.md) |
| [P-7-36](docs/pillars/P-7-engaging/OPEN.md#p-7-36) | Look: [step 22](.kiro/specs/zone-generator-district-looks/tasks.md) District looks | waiting | [step 22 archive](.kiro/specs/zone-generator-district-looks/archive.md) |
| [P-7-37](docs/pillars/P-7-engaging/OPEN.md#p-7-37) | Look: [step 27](.kiro/specs/zone-generator-random-placement/tasks.md)'s angled openings and tunnels | waiting | [step 27 archive](.kiro/specs/zone-generator-random-placement/archive.md) |

### P-8 World

| ID | Item | Status | Source |
|---|---|---|---|
| [P-8-1](docs/pillars/P-8-world/OPEN.md#p-8-1) | Multi-zone worlds and zone lines | waiting | [ROADMAP](ROADMAP.md); [step 12 archive](.kiro/specs/zone-generator-world-sockets/archive.md) |
| [P-8-2](docs/pillars/P-8-world/OPEN.md#p-8-2) | The `door` Socket kind is reserved, never made | open | [step 12 archive](.kiro/specs/zone-generator-world-sockets/archive.md) |
| [P-8-3](docs/pillars/P-8-world/OPEN.md#p-8-3) | An exact Mouth Socket; several dungeons per World | open | [step 12 archive](.kiro/specs/zone-generator-world-sockets/archive.md) |
| [P-8-4](docs/pillars/P-8-world/OPEN.md#p-8-4) | Outdoor-dungeon helpers still re-derive the landscape | open | [step 12 archive](.kiro/specs/zone-generator-world-sockets/archive.md) |

### P-9 Engineering

| ID | Item | Status | Source |
|---|---|---|---|
| [P-9-1](docs/pillars/P-9-engineering/OPEN.md#p-9-1) | No continuous integration (CI), releases, migrations or user docs | open | gap 2026-11-27 |
| [P-9-2](docs/pillars/P-9-engineering/OPEN.md#p-9-2) | No failure dashboard | open | gap 2026-11-27 |
| [P-9-3](docs/pillars/P-9-engineering/OPEN.md#p-9-3) | Heavy-run lock across agents | in flight ([project-docs task 5](.kiro/specs/project-docs/cards/05-tooling.md)) | the project-docs spec |
| [P-9-4](docs/pillars/P-9-engineering/OPEN.md#p-9-4) | Build time outside the gate | in flight ([step 33](.kiro/specs/zone-generator-layout-repair/tasks.md)) | [step 28 archive](.kiro/specs/test-speed/archive.md) |
| [P-9-5](docs/pillars/P-9-engineering/OPEN.md#p-9-5) | Split the 271 s corridor-clearance sweep test | open | steps [12](.kiro/specs/zone-generator-world-sockets/archive.md) and [28](.kiro/specs/test-speed/archive.md) archives |
| [P-9-6](docs/pillars/P-9-engineering/OPEN.md#p-9-6) | Stale "no `slow` marker" comments | open | [step 28 archive](.kiro/specs/test-speed/archive.md) |
| [P-9-7](docs/pillars/P-9-engineering/OPEN.md#p-9-7) | Cave draw time outside [`embed.py`](generators/topology/embed.py) | open | steps [27](.kiro/specs/zone-generator-random-placement/archive.md) and [29](.kiro/specs/zone-generator-cave-clumps/archive.md) archives |
| [P-9-8](docs/pillars/P-9-engineering/OPEN.md#p-9-8) | Slow outdoor-dungeon Draws (223 s worst) | in flight ([step 33](.kiro/specs/zone-generator-layout-repair/tasks.md)) | [step 19 archive](.kiro/specs/zone-generator-quality/archive.md) |
| [P-9-9](docs/pillars/P-9-engineering/OPEN.md#p-9-9) | Rough 30-room builds ~32 s: re-measure | open | [step 8 archive](.kiro/specs/zone-generator-room-walls/archive.md) |
| [P-9-10](docs/pillars/P-9-engineering/OPEN.md#p-9-10) | A parallel run that once hung | parked | [ROADMAP](ROADMAP.md) |
| [P-9-11](docs/pillars/P-9-engineering/OPEN.md#p-9-11) | Shared Python env drifts from the pins | open | [ROADMAP](ROADMAP.md) |
| [P-9-12](docs/pillars/P-9-engineering/OPEN.md#p-9-12) | PFS footer timestamp | parked | [ROADMAP](ROADMAP.md) |
| [P-9-13](docs/pillars/P-9-engineering/OPEN.md#p-9-13) | Inspector has no side-elevation view | open | [ROADMAP](ROADMAP.md) |
| [P-9-14](docs/pillars/P-9-engineering/OPEN.md#p-9-14) | [ZG-Req-33](.kiro/specs/zone-generator/requirements.md#introduction) cited but never written | open | found by [project-docs task 1](.kiro/specs/project-docs/cards/01-proposal.md) |
| [P-9-15](docs/pillars/P-9-engineering/OPEN.md#p-9-15) | Umbrella design and steering describe modules and behaviour the code doesn't have | in flight (project-docs) | found by [project-docs task 1](.kiro/specs/project-docs/cards/01-proposal.md) |
| [P-9-16](docs/pillars/P-9-engineering/OPEN.md#p-9-16) | Docs organised by history | in flight (project-docs) | the project-docs spec |

## Already fixed (dropped)

48 items recorded as open somewhere turned out to be fixed or superseded. Each pillar's
`OPEN.md` lists its own under "Fixed". These are the ones fixed by a single commit:

| Item | Fixed by | Pillar |
|---|---|---|
| `ZONE_PLAN_JSON_SCHEMA` lacks `winding`, `hall_length` | `2e325f3` ([step 31](.kiro/specs/zone-generator-district-races/tasks.md) task 9: District race and intrusion controls and LLM fields) | P-1 |
| Walk surface takes ceilings as floor | `e25abe6` ([step 7](.kiro/specs/zone-generator-dungeon-verticality/tasks.md) task 18: the walk gate stands on floors only) | P-2 |
| [Step 23](.kiro/specs/zone-generator-winding-tunnels/tasks.md) residuals: outline slit; decor clear width | `7566697` and `74ae74e` ([step 26](.kiro/specs/zone-generator-winding-control/tasks.md) task 10: a hairline gap counts as touching; decor aims its clear way where the gate does) | P-2 |
| Map outline depends on face order | `0af5124` (the outline no longer depends on face order) | P-4 |
| Socket markers infer the map frame | `bd394c6` ([step 13](.kiro/specs/zone-generator-site-sockets/tasks.md) task 9: the map SVG carries its frame) | P-4 |
| Race scale placeholders (`RACE_SCALE`) | `e5c3601` ([step 7](.kiro/specs/zone-generator-dungeon-verticality/tasks.md) task 17: rooms sized for their race at stock scale) | P-5 |
| No corridor RoomContexts (corridor lights) | `c498ef0` ([step 12](.kiro/specs/zone-generator-world-sockets/tasks.md) task 14: corridor RoomContexts, so decor lights corridors) | P-5 |
| `edit_outside_bands` waits on quality bands | `7466fef` ([step 19](.kiro/specs/zone-generator-quality/tasks.md): the quality gate in the pipeline) | P-6 |
| `keep_clear_shapes` duplicates `entrance_keep_clear` | `570ff4f` ([step 13](.kiro/specs/zone-generator-site-sockets/tasks.md) task 7: the outdoor dungeon keeps its rooms clear, not its hill) | P-7 |
| Same seed, different build in one process | `6781622` ([step 32](.kiro/specs/zone-generator-races-followups/tasks.md) task 2: the stock model cache is keyed by actor, not mesh) | P-7, P-9 |

The rest were closed by whole steps (for example multi-level dungeons by [step 7](.kiro/specs/zone-generator-dungeon-verticality/tasks.md), the district
look by [step 22](.kiro/specs/zone-generator-district-looks/tasks.md), the flooded-room square by [step 24](.kiro/specs/zone-generator-flooded-rooms/tasks.md), the rest of [M4](.kiro/specs/zone-generator/design.md#delivery-plan) by [step 18](.kiro/specs/zone-generator-edits/tasks.md), the SQL export by
[step 17](.kiro/specs/zone-generator-export/tasks.md)) and are listed with their step in the pillar files.
