# Architecture

How eq_s3d turns a request into an EverQuest zone. The code was read at master `c3d9b99`
(2026-11-27, the commit that opened the project-docs spec). This page is the map. Each pillar's
`DESIGN.md` under [`docs/pillars/`](pillars/README.md) covers its own part in more depth. History
(why things are the way they are) lives in each pillar's `DECISIONS.md`, not here. Terms in
capitals (District, Socket, Draw) are defined in the [glossary](#glossary) at the end. The rules
for IDs and links are in [`docs/STYLE.md`](STYLE.md).

## In one paragraph

A user describes a zone in words or sets the controls. The planner turns either one into a
**ZonePlan**. The expander turns the plan into a **ZoneSpec**: every room, corridor, light,
region, lock and material, as data. The builder turns the spec into files: a terrain mesh (TER),
a placement file (ZON) and textures (DDS), all packed into one `.eqg` archive. It also writes a
`.glb` preview for the browser and a `.zone.json` sidecar of advisory data. The pipeline then
walks the real mesh with a player-sized agent and checks the file format. A zone that fails is
thrown away and drawn again. Only a zone that passes is moved into `output/web/<zone>/v<n>/` and
shown.

## The pipeline

```
 web page / CLI
      |  mode = prompt | controls
      v
 ai/  planner ──────────────► ZonePlan  (validated, normalised)
      |  ai/expand.plan_to_spec
      v
 generators/  layout · districts · semantics · room dressing ──► ZoneSpec  (the IR)
      |
      |  pipeline.generate_validated
      |    1. quality.measure the spec; redraw a dull one (up to 32 Draws)
      |    2. ZoneBuilder.build in a scratch folder:
      |         World → Attach → Build (TER) → textures → Decor → Pack (.eqg, .glb, sidecar)
      |    3. gates: analyzer.traverse.validate (walk the mesh) + analyzer.rof2check (format)
      |       fail → reroll the stage to blame (decor, rooms, else a fresh seed); pinned seed → error
      |    4. pass → map outline, SVG map, EQ map files, saved inputs; move to v<n>/
      v
 output/web/<zone>/v<n>/   ──► rebuild / edit (v<n+1>) · export (export/<short>/) · room view
```

| Stage | Code | In | Out |
|---|---|---|---|
| Request | [`server/app.py`](../server/app.py) route `/api/generate`; [`main.py`](../main.py) command `generate` | prompt text or control values, seeds | a call to the planner |
| Plan | [`ai/planner.py`](../ai/planner.py) (`RulePlanner` by default, `LLMPlanner` when an API key is set); [`ai/schema.py`](../ai/schema.py) `ZonePlan.from_controls` and `validate` | words or controls | `ZonePlan` |
| Expand | [`ai/expand.py`](../ai/expand.py) `plan_to_spec` | `ZonePlan`, seed, rooms seed | `ZoneSpec` |
| Layout | [`generators/layout.py`](../generators/layout.py) `LayoutGenerator`, behind [`generators/layout_engine.py`](../generators/layout_engine.py): `ClassicEngine` (TinyKeep) or `GraphEngine` (graph rewriting from [`rules/topology/`](../rules/topology)) | zone type, room count, race, theme, verticality, hall length | rooms, corridors, Levels, pacing roles, Gates |
| Districts | [`generators/districts.py`](../generators/districts.py) | the room graph | `DistrictSpec` list, Threshold corridors |
| Content | [`generators/semantics.py`](../generators/semantics.py), [`generators/wall_styles.py`](../generators/wall_styles.py), [`generators/room_layouts.py`](../generators/room_layouts.py), [`generators/room_scales.py`](../generators/room_scales.py), [`generators/transitions.py`](../generators/transitions.py) | theme, race, tint, Districts | room types, palettes, lights, regions, Outlines, Features, Transitions |
| Landscape | [`generators/wilderness/`](../generators/wilderness) (Design_Matrix, synthesis, bowl), [`generators/outdoor_dungeon.py`](../generators/outdoor_dungeon.py), [`generators/envelope.py`](../generators/envelope.py) | biome, edges, seed | the `wilderness` payload on the spec; an outdoor dungeon's Envelope |
| Quality | [`generators/quality.py`](../generators/quality.py) | the spec's room graph | `QualityReport` (pass, or degraded with the metrics that fell out of band) |
| Build | [`generators/builder.py`](../generators/builder.py) `ZoneBuilder.build` | the spec, stage seeds | TER, ZON, DDS, `.eqg`, `.glb`, `.zone.json`, stage hand-offs |
| Gate | [`analyzer/traverse.py`](../analyzer/traverse.py) `validate`; [`analyzer/rof2check.py`](../analyzer/rof2check.py) `check_eqg` | the built `.eqg` and the spec | `TraversalReport`, `FormatReport` |
| Post-pass | [`generators/mapgeom.py`](../generators/mapgeom.py), [`generators/mapview.py`](../generators/mapview.py), [`generators/eqmap.py`](../generators/eqmap.py) | the accepted TER | `<name>.map.svg`, `maps/<name>.txt` and its layers `_1` to `_3` |
| Versions | [`generators/rebuild.py`](../generators/rebuild.py), [`generators/edits.py`](../generators/edits.py), [`generators/resize.py`](../generators/resize.py), [`ai/edits.py`](../ai/edits.py) | a version's saved spec and stages | the next version `v<n+1>` |
| Export | [`generators/export.py`](../generators/export.py), [`generators/sqlexport.py`](../generators/sqlexport.py), [`analyzer/zonelist.py`](../analyzer/zonelist.py) | a version, a known short name | `export/<short>/`: renamed `.eqg`, maps, `.sql`, `INSTALL.txt`, a bundle zip |

## Zone types and backends

| Zone type | Built by | Layout | Gate |
|---|---|---|---|
| `dungeon` | `BoxBackend` ([`generators/geometry.py`](../generators/geometry.py)) | Graph (default) or Classic | rooms reached from the safe point, corridors, Features, placed models |
| `city` | `BoxBackend` | Classic | the same |
| `wilderness` | `TerrainBackend`, which calls [`generators/wilderness/build.py`](../generators/wilderness/build.py) | none (open landscape) | the bowl gate: no fall out of the world, and the Spawn reaches the playable ground |
| `outdoor_dungeon` | `TerrainBackend`: a wilderness host with a box dungeon merged under a hill | Graph (default) or Classic, inside an Envelope | the bowl gate, plus every room reached from the outdoor Spawn |

All four types are defined and enabled ([`generators/zone_types.py`](../generators/zone_types.py)). Backends sit in a registry
([`generators/backends.py`](../generators/backends.py)); an unknown zone type falls back to the box backend. There is no cave
backend: a cave is the `cave` Purpose of a dungeon, drawn with the `rough` wall style.

## The ZoneSpec (the IR)

The ZoneSpec lives in [`generators/zone_spec.py`](../generators/zone_spec.py). Everything after the planner reads and writes
this one structure. It round-trips through JSON: `<name>.spec.json` is saved with every build.

| Part | What it holds |
|---|---|
| zone | `name`, `zone_type`, `style_profile`, `seed`, `rooms_seed`, `decor_seed`, `room_decor_seeds`, `dungeon_theme` (the Purpose), `dungeon_race`, `elemental_tint`, `winding`, `hall_length`, `safe_point`, `ambient_light` |
| `rooms` | `RoomSpec`: box (centre, size, floor height), materials, `role` and `graph_depth` (pacing), `semantic_type`, `kind`, `district`, `outline` (the wall style's shape), `features`, `pois`, advisory hints |
| `corridors` | `CorridorSpec`: ends, floor heights, width, height, `steps` (stairs), `bridge`, `rough`, `wind` and `path` (winding), `transition`, `threshold`, `drop` (one-way) |
| `lights`, `regions`, `materials` | ZON lights; water, lava and zone-line volumes; `MaterialSpec` (texture, shader, colour, texel density) |
| `gates` | `GateSpec`: a lock on a corridor and its key room. Advisory; it becomes an EQEmu door on Export |
| `districts` | `DistrictSpec`: Purpose, race, rooms, climax, Threshold corridor, palette, light mood |
| `wilderness`, `layout`, `sites`, `decor` | the landscape payload; the layout engine's record; Site and Decor settings |

## Build stages and hand-offs

A build runs **World → Attach → Build → Decor → Pack** ([`generators/world.py`](../generators/world.py),
[`generators/stages.py`](../generators/stages.py), [`generators/builder.py`](../generators/builder.py)). Each stage is a function of its seed and the
earlier stages' output. Each saves that output beside the build:

| File | Stage | Read back by |
|---|---|---|
| `<name>.world.json` | World: terrain grid, Landform, Sockets (`root`, `hillside`, `ground`, `site`) | `scripts/stage.py` |
| `<name>.attach.json` | Attach: rooms and Sites on their Sockets, terrain edits | `scripts/stage.py` |
| `<name>.rooms.json` and the RoomContexts | the Rooms → Decor hand-off: what each room looks like to placement | room view, decor rebuild |
| `<name>.spec.json`, `<name>.request.json` | the spec that was built, and the request with the seeds used | rebuild, edits, export |
| `<name>.zone.json` | the sidecar: advisory data (pacing, Gates, POIs, quality, format, Districts, seeds, version) | the web page, export |
| `<name>.eqg`, `<name>.glb` | Pack: the client archive and the browser preview | the client, the web page, gates |
| `<name>.map.svg`, `maps/<name>*.txt` | the maps made after the gates pass | the web page, the client's map window |

Three seeds drive the stages: `seed` (World, trees), `rooms_seed` (rooms, Sites) and
`decor_seed` (Props). Each defaults to `seed`. On a gate failure the pipeline rerolls only the
stage it blames, at most twice per World.

## Module map

| Folder | Owns | Biggest files (lines) |
|---|---|---|
| [`core/`](../core) | binary formats: the PFS archive (with EQ's CRC), TER, ZON, EQG assembly and GLB, the WLD reader; [`core/paths.py`](../core/paths.py) keeps writes inside the output folder | [`core/pfs.py`](../core/pfs.py) 601, [`core/eqg.py`](../core/eqg.py) 458 |
| [`analyzer/`](../analyzer) | stock-zone measurement, the inspector, the walk gate, the format gate, known short names, placed-model footprints | [`analyzer/traverse.py`](../analyzer/traverse.py) 3854, [`analyzer/footprints.py`](../analyzer/footprints.py) 1171, [`analyzer/rof2check.py`](../analyzer/rof2check.py) 808 |
| [`ai/`](../ai) | prompt and controls → `ZonePlan`; chat edits → edit ops; no geometry | [`ai/schema.py`](../ai/schema.py) 755, [`ai/edits.py`](../ai/edits.py) 622, [`ai/rule_planner.py`](../ai/rule_planner.py) 579 |
| [`generators/`](../generators) | the IR, layout, content, geometry, textures, decor, Sites, trees, maps, quality, pipeline, versions, export | [`generators/layout.py`](../generators/layout.py) 4643, [`generators/decor/placement.py`](../generators/decor/placement.py) 2532, [`generators/geometry.py`](../generators/geometry.py) 2147, [`generators/topology/embed.py`](../generators/topology/embed.py) 2068 |
| [`rules/`](../rules) | data the generator reads, checked on load: [`rules/topology/`](../rules/topology), [`rules/walls/`](../rules/walls), [`rules/rooms/`](../rules/rooms), [`rules/sites/`](../rules/sites), [`rules/decor/`](../rules/decor) | [`rules/decor/catalogue.json`](../rules/decor/catalogue.json) (4,651 stock models) |
| [`styles/`](../styles) | measured style profiles per theme and biome | [`styles/dungeon.json`](../styles/dungeon.json) (10 zones), [`styles/cave.json`](../styles/cave.json) (8), [`styles/city.json`](../styles/city.json) (6) |
| [`server/`](../server) | the FastAPI app: generate, rebuild, edit, versions, room decor, export, version | [`server/app.py`](../server/app.py) 1967 |
| [`web/`](../web) | the browser app (TypeScript, Three.js) | [`web/src/main.ts`](../web/src/main.ts) 1436, [`web/src/roomview.ts`](../web/src/roomview.ts) 768, [`web/src/api.ts`](../web/src/api.ts) 698 |
| [`scripts/`](../scripts) | stock surveys, sweeps, the stage runner, worktree helpers, [`scripts/task_status.py`](../scripts/task_status.py) | 31 scripts |
| [`tests/`](../tests) | pytest and Hypothesis tests, in tiers (quick, full, gate) | — |

## North-star rules

These come from [`.kiro/steering/project.md`](../.kiro/steering/project.md) "North-star intent"
and bind every pillar.

1. **Indistinguishable from a hand-crafted zone**: natural geometry over clean architecture.
2. **Classic–PoP look by default.** That era ships as `.s3d`/WLD. We read both formats and write `.eqg`.
3. **Navigable**: every room is reachable by an EQ-scale player (slope at most 40°, step-up at most 3 u), proven on the mesh.
4. **No manual modelling**: everything comes from prompts and parameters. The one exception is stock Props copied from the user's own install ([umbrella decision 31](../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)).
5. **No API by default**: the rule planner and procedural textures need no keys and no network.
6. **Randomness is a feature**: a fresh seed per generate unless one is pinned; a pinned seed reproduces.
7. **Under about 5 minutes per generate.**
8. **Suggestions stay suggestions**: pacing, Gates, POIs and hints ride in the sidecar, never in geometry or collision.
9. **Z is up**, as in EverQuest; the web camera is set to match.
10. **The tool writes only under `output/`.** Installing into the client is the user's manual step.

## Product requirements

The product requirements are the umbrella spec's
[`.kiro/specs/zone-generator/requirements.md`](../.kiro/specs/zone-generator/requirements.md),
written `ZG-Req-<n>`. Each pillar's `PLAN.md` turns the ones it serves into pillar requirements
(`P-<n>-Req-<k>`) and names the parent. Draft requirements that the umbrella hasn't adopted
yet are listed in [the pillar README](pillars/README.md#proposed-product-requirements).

| Pillar | Product requirements |
|---|---|
| [P-1 Web app and controls](pillars/P-1-web-app/PLAN.md) | [ZG-Req-1](../.kiro/specs/zone-generator/requirements.md#requirement-1-explicit-generation-modes), [ZG-Req-2](../.kiro/specs/zone-generator/requirements.md#requirement-2-control-coverage-and-plan-normalisation), [ZG-Req-3](../.kiro/specs/zone-generator/requirements.md#requirement-3-zone-type-availability) |
| [P-2 Traversable](pillars/P-2-traversable/PLAN.md) | [ZG-Req-4](../.kiro/specs/zone-generator/requirements.md#requirement-4-traversability-gate), [ZG-Req-5](../.kiro/specs/zone-generator/requirements.md#requirement-5-walkable-connections), [ZG-Req-6](../.kiro/specs/zone-generator/requirements.md#requirement-6-wilderness-terrain-alignment), [ZG-Req-7](../.kiro/specs/zone-generator/requirements.md#requirement-7-natural-geometry-style-for-dungeons) |
| [P-3 Usable in RoF2 and EQEmu](pillars/P-3-rof2-eqemu/PLAN.md) | [ZG-Req-8](../.kiro/specs/zone-generator/requirements.md#requirement-8-export-time-short-name-takeover), [ZG-Req-9](../.kiro/specs/zone-generator/requirements.md#requirement-9-tier-1-rof2-format-check), [ZG-Req-10](../.kiro/specs/zone-generator/requirements.md#requirement-10-tier-2-eqemu-sql-export), [ZG-Req-11](../.kiro/specs/zone-generator/requirements.md#requirement-11-format-and-ir-round-trips) |
| [P-4 True-layout artifacts](pillars/P-4-true-layout/PLAN.md) | [ZG-Req-12](../.kiro/specs/zone-generator/requirements.md#requirement-12-mesh-derived-outline), [ZG-Req-13](../.kiro/specs/zone-generator/requirements.md#requirement-13-everquest-in-client-map-file), [ZG-Req-14](../.kiro/specs/zone-generator/requirements.md#requirement-14-true-layout-map-and-artifacts-in-the-web_app) |
| [P-5 EverQuest look and feel](pillars/P-5-look-and-feel/PLAN.md) | [ZG-Req-15](../.kiro/specs/zone-generator/requirements.md#requirement-15-era-fidelity-and-measured-conformance), [ZG-Req-16](../.kiro/specs/zone-generator/requirements.md#requirement-16-procedural-normal-maps), [ZG-Req-17](../.kiro/specs/zone-generator/requirements.md#requirement-17-textured-preview), [ZG-Req-33](../.kiro/specs/zone-generator/requirements.md#introduction) |
| [P-6 Iterative feedback](pillars/P-6-iterative-feedback/PLAN.md) | [ZG-Req-18](../.kiro/specs/zone-generator/requirements.md#requirement-18-sessions-and-feedback-interpretation), [ZG-Req-19](../.kiro/specs/zone-generator/requirements.md#requirement-19-edit-application-and-acceptance), [ZG-Req-20](../.kiro/specs/zone-generator/requirements.md#requirement-20-history-undo-and-redo) |
| [P-7 Engaging every time](pillars/P-7-engaging/PLAN.md) | [ZG-Req-21](../.kiro/specs/zone-generator/requirements.md#requirement-21-composed-solvable-layout), [ZG-Req-22](../.kiro/specs/zone-generator/requirements.md#requirement-22-topology-control), [ZG-Req-23](../.kiro/specs/zone-generator/requirements.md#requirement-23-districts), [ZG-Req-24](../.kiro/specs/zone-generator/requirements.md#requirement-24-quality-gate), [ZG-Req-25](../.kiro/specs/zone-generator/requirements.md#requirement-25-quality_degraded-is-always-visible) |
| [P-8 World](pillars/P-8-world/PLAN.md) | proposed [ZG-Req-34](pillars/README.md#zg-req-34) to [ZG-Req-37](pillars/README.md#zg-req-37) |
| [P-9 Engineering](pillars/P-9-engineering/PLAN.md) | [ZG-Req-26](../.kiro/specs/zone-generator/requirements.md#requirement-26-determinism-and-fresh-seed-randomness) to [ZG-Req-32](../.kiro/specs/zone-generator/requirements.md#requirement-32-settled-design-constraints); proposed [ZG-Req-38](pillars/README.md#zg-req-38) to [ZG-Req-42](pillars/README.md#zg-req-42) |

[ZG-Req-33](../.kiro/specs/zone-generator/requirements.md#introduction) (the `cave` Purpose) is cited in the umbrella's introduction but its text was never
written ([P-9-14](pillars/P-9-engineering/OPEN.md#p-9-14)).

## Where to read more

- The pillars and how the work is spread across them: [`docs/pillars/README.md`](pillars/README.md)
- Everything still open: [`OPEN.md`](../OPEN.md)
- Format gotchas and hard-won lessons: [`.kiro/steering/lessons-learned.md`](../.kiro/steering/lessons-learned.md)
- Authoring guides: [`docs/TOPOLOGY_RULES.md`](TOPOLOGY_RULES.md), [`docs/DECOR_RULES.md`](DECOR_RULES.md)
- Research verdicts: [`docs/RESEARCH.md`](RESEARCH.md)
- The original target design, partly out of date (each pillar's `DESIGN.md` says what is true now): [`.kiro/specs/zone-generator/design.md`](../.kiro/specs/zone-generator/design.md)
- House rules for these docs: [`docs/STYLE.md`](STYLE.md)

## Glossary

The umbrella spec has its own [glossary](../.kiro/specs/zone-generator/requirements.md#glossary)
that writes names with underscores (Zone_Plan, Traversal_Validator). These docs use the code's
names where one exists. Where the umbrella's word differs, it is given in brackets.

### Project and process

| Term | Meaning |
|---|---|
| Umbrella spec | [`.kiro/specs/zone-generator/`](../.kiro/specs/zone-generator): the whole-system requirements and target design. Its requirements are the product requirements (`ZG-Req-<n>`) |
| Pillar | One outcome the project serves (P-1 to P-9). Each has a folder under [`docs/pillars/`](pillars) |
| Step | One unit of roadmap work with its own spec under [`.kiro/specs/`](../.kiro/specs). Steps are numbered 1 to 33, plus 1b. Its slice ID is `S-<step>` (for example S-31), and its requirements are written `S-31-Req-2` |
| Slice | A step seen from the pillar it served. "Slice" and "step" name the same spec |
| Milestone ([M0](../.kiro/specs/zone-generator-m0-hygiene/tasks.md) to [M6](../.kiro/specs/zone-generator/design.md#delivery-plan)) | The umbrella's original delivery plan ([Delivery Plan](../.kiro/specs/zone-generator/design.md#delivery-plan)). M0 and [M1](../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) were built as specs; [step 1b](../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md) was [M2](../.kiro/specs/zone-generator/design.md#delivery-plan); the rest was replaced by numbered steps |
| Wave | A group of tasks inside the [M1](../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) spec (waves 1 to 6) |
| Pre-spec phase | Work done before specs existed (Phase 0 to 3, the web app, layout). Described in [`ROADMAP.md`](../ROADMAP.md) [Completed-work detail](../ROADMAP.md#completed-work-detail) |
| Card, card format | A spec whose `tasks.md` is an index with one card file per task. Rules in [`.kiro/steering/project.md`](../.kiro/steering/project.md) "Card-format specs" |
| Archive | A spec's `archive.md`: what landed, its numbered decisions and its follow-ups |
| Acceptance pass, look | The manual check in the 3D view listed in [`docs/ACCEPTANCE.md`](ACCEPTANCE.md). "Look skipped" means the user chose not to do it |
| Integration step | The single step, run from the main checkout, that writes [`ROADMAP.md`](../ROADMAP.md), [`README.md`](../README.md) and [`tasks/README.md`](../tasks/README.md) after a branch lands |
| Worktree | A separate git checkout for one agent's branch ([`scripts/new-worktree.ps1`](../scripts/new-worktree.ps1)) |
| Quick, full, gate tiers | The three ways the test suite is run; see [P-9 Engineering design](pillars/P-9-engineering/DESIGN.md#tests) |
| Sweep | A script or test that builds many seeds or settings and counts failures |
| Hypothesis | The property-based testing library the tests use; its `quick` and `thorough` profiles set how many examples it tries |
| Property N | A numbered correctness property in the umbrella design, for example [Property 38](../.kiro/specs/zone-generator/design.md#property-38-conformance-is-measured-and-in-range) |
| [Known Limitation](../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them) N | A numbered entry in the umbrella design's [Known Limitations](../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them) list |

### The pipeline and its files

| Term | Meaning |
|---|---|
| CLI | The command line: `python main.py` with its commands (`generate`, `export`, `--edit`) |
| API, API key | Here, a paid online service such as a language model or an image generator, and the key that unlocks it. The tool needs neither by default |
| ZonePlan [Zone_Plan] | The small plan the planner makes from words or controls ([`ai/schema.py`](../ai/schema.py)) |
| ZoneSpec, IR [Zone_Spec] | The full description of a zone as data, which every later stage reads ([`generators/zone_spec.py`](../generators/zone_spec.py)). IR stands for intermediate representation |
| Planner | Turns a prompt into a ZonePlan: `RulePlanner` (keyword rules, no API) or `LLMPlanner` (a large language model, LLM, optional) |
| Draw | One candidate plan-and-layout the pipeline makes for a seed before building it |
| Gate | (1) The checks a build must pass to be shown: the walk gate and the format gate. (2) An advisory lock on a corridor plus the room that holds its key (`GateSpec`). The sense is clear from context; a lock is always written "Gate" with a capital |
| Walk gate [Traversal_Validator] | [`analyzer/traverse.py`](../analyzer/traverse.py) `validate`: floods the built mesh from the safe point with a player-sized agent and fails if any room is unreachable |
| Bowl gate | The walk gate's check for landscapes: no fall out of the world, and the Spawn reaches the playable ground |
| Format gate [Format_Checker] | [`analyzer/rof2check.py`](../analyzer/rof2check.py) `check_eqg`: the named checks that the `.eqg` reads back and is well formed (Tier 1) |
| Tier 1, Tier 2 | The two levels of "usable in RoF2" ([umbrella decision 4](../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)): Tier 1 is the automated format gate; Tier 2 is the EQEmu SQL plus a manual load in the game |
| Blame, reroll | On a gate failure the pipeline guesses which stage caused it and draws a new seed for that stage only |
| Pinned seed | A seed the user gave. It is never swapped; if it fails, the generate fails |
| Quality bands, degraded | Ranges the quality metrics must fall in. A build outside them is "degraded": still shown, with a banner listing the metrics |
| Version | One build of a zone, stored in `output/web/<zone>/v<n>/`. Rebuilds and edits make the next version |
| Partial rebuild | A rebuild that reuses the parent version's saved stages and redoes only decor and later steps |
| Sidecar | The `<name>.zone.json` file next to a build, holding advisory data (pacing, Gates, POIs, quality, seeds) |
| Advisory data | Hints for a human author (pacing, Gates, POIs). They ride in the sidecar and never change geometry or collision |
| Build_Name | The lowercase name every file of a build carries: `gen_<timestamp>_<hex>`, or the CLI's name |
| Export | Copying a build under an existing client zone's short name, with SQL and install notes, into `export/<short>/` |
| Short name, takeover | A zone's internal client name (`arena`). RoF2's zone list is fixed in the client, so a new zone is installed by taking over an existing short name |
| Known_Zone_List | The 496 RoF2 short names the tool knows ([`analyzer/data/rof2_zones.json`](../analyzer/data/rof2_zones.json)) |
| Stage, hand-off | One of World, Attach, Build, Decor, Pack; the JSON file each saves for the next |

### File formats and games

| Term | Meaning |
|---|---|
| EQ, RoF2 | EverQuest; Rain of Fear 2, the client version the tool targets |
| EQEmu | The open-source EverQuest server. A zone needs rows in its database (`zone`, `doors`) to be entered |
| Classic–PoP | The game's eras from launch to Planes of Power (2002), the default look |
| GoD | Gates of Discord (2003), the first era to ship zones as `.eqg` |
| `.s3d`, WLD | The Classic–PoP zone archive and the mesh format inside it. Read by [`core/wld.py`](../core/wld.py), never written |
| `.eqg` | The later zone archive the tool writes: a PFS archive holding a TER, a ZON and textures |
| PFS | The archive container used by both `.s3d` and `.eqg`, with EQ's own filename CRC (a checksum) |
| TER | The terrain mesh file inside an `.eqg`: every triangle, its collision flag and material |
| ZON | The placement file inside an `.eqg`: models, objects, lights, regions |
| MOD, `.mod` | A model file (a tree, a Structure, a stock Prop) placed by the ZON |
| DDS | The texture image format the client reads |
| GLB | The 3D file the browser preview loads (`<name>.glb`) |
| `AWT` region | A ZON region that marks water |
| `ztype` | An EQEmu `zone` table column for the zone's type (indoor, outdoor and so on) |
| u | One EverQuest unit, about one foot. A player is about 6 u tall |
| H | The body height of a race in units. Room and corridor sizes are given in multiples of H |

### Layout and content

| Term | Meaning |
|---|---|
| Classic layout, TinyKeep | The original layout engine: scatter rooms, push them apart, join them by a spanning tree plus some loops |
| Graph layout, rule set | The default layout engine: grows a room graph by rewriting rules read from TOML files under [`rules/topology/`](../rules/topology) (rule sets such as `classic_eq` and `warren`) |
| Layer (rules) | A TOML file merged over a base rule file (by theme, race, request) |
| Room graph | Rooms as nodes and corridors as edges |
| Pacing roles | Labels from the room graph: entrance, hub, dead end, climax |
| Level | A whole-number floor height band in a Graph layout. Stairs and Bridges join Levels |
| Verticality | How many Levels a layout uses: flat, moderate or dramatic |
| Winding | The 0 to 2 scalar for how much rough corridors wander |
| Hall length | The 0.5 to 3 scalar for how far apart rooms sit |
| Bridge | A corridor that crosses over a lower room through a shaft in its ceiling |
| Switchback | A stair of two half-height flights and one landing |
| Drop | A one-way link: a fall of 6 to 80 u between Districts, never the only way back |
| Purpose [theme, archetype] | What a dungeon is for (`fortress`, `tomb`, `cave` and 9 more). Stored in the legacy field `dungeon_theme` |
| Race | Who built the place; sets scale through H. Stored in `dungeon_race` |
| Element [tint] | A water, lava or ice overlay. Stored in `elemental_tint` |
| District | A group of rooms with one Purpose, race, palette, light mood and climax |
| Threshold | The corridor that joins two Districts |
| Intrusion, breach | A younger District breaking into its host District through up to 3 breaches |
| Box | A room's rectangle from the layout. Shared code (routing, Gates) reads only the Box |
| Outline, Cell | The shaped floor plan drawn inside a Box, made from Cells |
| Wall style | `built` (straight), `hewn` (uneven facets) or `rough` (Voronoi cells, cave-like) |
| Throat | The stretch of floor a doorway needs; also, in caves, a short link where two rooms open into each other |
| Scales: Finish, Structure, Clutter | Three 0 to 10 scores per room. Finish sets the wall style; Structure and Clutter set how much solid structure and loose stuff a room holds |
| Coherence | How strongly a room's Scales lean toward its neighbours' |
| Feature | Solid structure in a room: pillar, boulder, dais and kin. The gate judges it |
| Spine | The paths joining a room's doors; Features keep off it |
| Transition: Seam, Frame, Breach | What a corridor carries where two wall styles meet |
| POI | Point of interest: an advisory spot in the sidecar |
| Prop | A stock model copied from the user's install and placed as decor |
| Catalogue | [`rules/decor/catalogue.json`](../rules/decor/catalogue.json): every stock model with its tags (Category, kind, Mount, Set) |
| RoomContext | How decor placement reads a room: its floor, walls and doors, the same way the gate sees them |
| Site | A small built place in a wilderness: camp, hut, farmstead, watchtower, shrine, ruin |
| Structure | A building or object a Site is made of, written as a `.mod` |
| Group | A cluster of point Sockets where Sites gather, as stock hamlets do |
| Inhabitant | Who lives at a Site (human, orc, gnoll, centaur); weights the kinds drawn |
| Footprint | The ground a placed model occupies; the gate checks it doesn't block the way (`footprint_cut`) |
| Enterable | A placed model the player can walk into; its opening must be at least 8 u wide and high |

### Landscape and World

| Term | Meaning |
|---|---|
| Wilderness | An open outdoor zone (`wilderness`), built as a landscape, not rooms |
| Design_Matrix | The coarse grid of cell types (plains, river, cliff, rim, lava, zone-line gap, water) that shapes a wilderness |
| Bowl | The wilderness edge: mountain slopes and invisible walls that keep the player in |
| Spawn | Where the player enters a landscape |
| Safe point | Where the player appears; the walk gate floods from it |
| World | The first stage: the terrain, water, Spawn, Landform and Sockets of one zone ([`generators/world.py`](../generators/world.py)) |
| Socket | A typed attach point the World offers: `root`, `hillside`, `ground`, `site`, `door` (reserved) |
| Landform | A placed land shape, such as an outdoor dungeon's host hill (Host_Hill) |
| Envelope | The 3D space an outdoor dungeon must fit in: the hill's footprint, a floor limit, the surface less a Rock_Cover |
| Entrance: Apron, Tunnel, Mouth | An outdoor dungeon's way in: a trench (Apron), a one-cell Tunnel into the hill, and its opening (Mouth) |
| Zone line | A crossing from one zone into another. Not built yet |
