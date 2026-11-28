# Architecture

How eq_s3d turns a request into an EverQuest zone, as the code stands at master `c3d9b99`
(2026-11-27). This page is the map; each pillar's `DESIGN.md` under [`pillars/`](pillars/README.md)
goes into its own part. History (why things are the way they are) lives in the pillars'
`DECISIONS.md`, not here.

## In one paragraph

A user describes a zone in words or sets the controls. The planner turns either into a
**ZonePlan**. The expander turns the plan into a **ZoneSpec**: every room, corridor, light,
region, lock and material, as data. The builder turns the spec into files: a terrain mesh (TER),
a placement file (ZON), textures (DDS), all packed into one `.eqg` archive, plus a `.glb` preview
for the browser and a `.zone.json` sidecar of advisory data. The pipeline then walks the real mesh
with a player-sized agent and checks the file format; a zone that fails is thrown away and drawn
again. Only a zone that passes is moved into `output/<zone>/v<n>/` and shown.

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

| Step | Code | In | Out |
|---|---|---|---|
| Request | `server/app.py` `/api/generate`, `main.py generate` | prompt text or control values, seeds | a call to the planner |
| Plan | `ai/planner.py` (`RulePlanner` default, `LLMPlanner` if a key is set), `ai/schema.py` `ZonePlan.from_controls` / `validate` | words or controls | `ZonePlan` |
| Expand | `ai/expand.py` `plan_to_spec` | `ZonePlan`, seed, rooms seed | `ZoneSpec` |
| Layout | `generators/layout.py` `LayoutGenerator` behind `generators/layout_engine.py` (`ClassicEngine` TinyKeep, `GraphEngine` graph rewriting from `rules/topology/`) | zone type, room count, race, theme, verticality, hall length | rooms, corridors, Levels, pacing roles, gates |
| Districts | `generators/districts.py` | the room graph | `DistrictSpec` list, Threshold corridors |
| Content | `generators/semantics.py`, `wall_styles.py`, `room_layouts.py`, `room_scales.py`, `transitions.py` | theme, race, tint, Districts | room types, palettes, lights, regions, Outlines, Features, Transitions |
| Landscape | `generators/wilderness/` (Design_Matrix, synth, bowl), `generators/outdoor_dungeon.py`, `generators/envelope.py` | biome, edges, seed | the `wilderness` payload on the spec; an outdoor dungeon's Envelope |
| Quality | `generators/quality.py` | the spec's room graph | `QualityReport` (pass, or degraded with the metrics out of band) |
| Build | `generators/builder.py` `ZoneBuilder.build` | the spec, stage seeds | TER, ZON, DDS, `.eqg`, `.glb`, `.zone.json`, stage hand-offs |
| Gate | `analyzer/traverse.py` `validate`, `analyzer/rof2check.py` `check_eqg` | the built `.eqg` and the spec | `TraversalReport`, `FormatReport` |
| Post-pass | `generators/mapgeom.py`, `mapview.py`, `eqmap.py` | the accepted TER | `<name>.map.svg`, `maps/<name>.txt` and `_1.._3` layers |
| Versions | `generators/rebuild.py`, `generators/edits.py`, `generators/resize.py`, `ai/edits.py` | a version's saved spec and stages | the next version `v<n+1>` |
| Export | `generators/export.py`, `generators/sqlexport.py`, `analyzer/zonelist.py` | a version, a known short name | `export/<short>/`: renamed `.eqg`, maps, `.sql`, `INSTALL.txt`, bundle zip |

## Zone types and backends

| Zone type | Built by | Layout | Gate |
|---|---|---|---|
| `dungeon` | `BoxBackend` (`generators/geometry.py`) | Graph (default) or Classic | rooms reached from the safe point, corridors, Features, placed models |
| `city` | `BoxBackend` | Classic | the same |
| `wilderness` | `TerrainBackend` → `generators/wilderness/build.py` | none (open landscape) | the bowl gate (no fall out, Spawn reaches the playable ground) |
| `outdoor_dungeon` | `TerrainBackend`: a wilderness host with a box dungeon merged under a hill | Graph (default) or Classic, inside an Envelope | the bowl gate plus every room from the outdoor Spawn |

All four are defined and enabled (`generators/zone_types.py`). Backends are a registry
(`generators/backends.py`); an unknown zone type falls back to the box backend. There is no cave
backend: a cave is the `cave` Purpose of a dungeon, drawn with the `rough` wall style.

## The ZoneSpec (the IR)

`generators/zone_spec.py`. Everything after the planner reads and writes this one structure, and
it round-trips through JSON (`<name>.spec.json` is saved with every build).

| Part | What it holds |
|---|---|
| zone | `name`, `zone_type`, `style_profile`, `seed`, `rooms_seed`, `decor_seed`, `room_decor_seeds`, `dungeon_theme` (the Purpose), `dungeon_race`, `elemental_tint`, `winding`, `hall_length`, `safe_point`, `ambient_light` |
| `rooms` | `RoomSpec`: box (centre, size, floor height), materials, `role` and `graph_depth` (pacing), `semantic_type`, `kind`, `district`, `outline` (wall style shape), `features`, `pois`, advisory hints |
| `corridors` | `CorridorSpec`: ends, floor heights, width, height, `steps` (stairs), `bridge`, `rough`, `wind` / `path` (winding), `transition`, `threshold`, `drop` (one-way) |
| `lights`, `regions`, `materials` | ZON lights; water/lava/zoneline volumes; `MaterialSpec` (texture, shader, colour, texel density) |
| `gates` | `GateSpec`: a lock on a corridor and its key room (advisory; becomes an EQEmu door on Export) |
| `districts` | `DistrictSpec`: Purpose, race, rooms, climax, Threshold corridor, palette, light mood |
| `wilderness`, `layout`, `sites`, `decor` | the landscape payload; the layout engine's record; Site and Decor settings |

## Build stages and hand-offs

A build runs **World → Attach → Build → Decor → Pack** (`generators/world.py`,
`generators/stages.py`, `generators/builder.py`). Each stage is a function of its seed and the
earlier stages' output, and saves that output beside the build:

| File | Stage | Read back by |
|---|---|---|
| `<name>.world.json` | World: terrain grid, Landform, Sockets (`root`, `hillside`, `ground`, `site`) | `scripts/stage.py` |
| `<name>.attach.json` | Attach: rooms and Sites on their Sockets, terrain edits | `scripts/stage.py` |
| `<name>.rooms.json` + RoomContexts | Rooms → Decor hand-off: what each room looks like to placement | room view, decor rebuild |
| `<name>.spec.json`, `<name>.request.json` | the spec built and the request with the seeds used | rebuild, edits, export |
| `<name>.zone.json` | sidecar: advisory data (pacing, gates, POIs, quality, format, Districts, seeds, version) | the web page, export |
| `<name>.eqg`, `<name>.glb` | Pack: the client archive and the browser preview | the client, the web page, gates |
| `<name>.map.svg`, `maps/<name>*.txt` | post-pass maps | the web page, the client map window |

Three seeds drive the stages: `seed` (World, trees), `rooms_seed` (rooms, Sites), `decor_seed`
(Props). Each defaults to `seed`. On a gate failure the pipeline rerolls only the stage it blames,
at most twice per World.

## Module map

| Folder | Owns | Biggest files (lines) |
|---|---|---|
| `core/` | binary formats: PFS archive (EQ CRC), TER, ZON, EQG assembly and GLB, WLD reader; `paths.py` output confinement | `pfs.py` 601, `eqg.py` 458 |
| `analyzer/` | stock-zone measurement, inspector, the walk gate, the format gate, known short names, placed-model footprints | `traverse.py` 3854, `footprints.py` 1171, `rof2check.py` 808 |
| `ai/` | prompt and controls → `ZonePlan`; chat edits → ops; no geometry | `schema.py` 755, `edits.py` 622, `rule_planner.py` 579 |
| `generators/` | the IR, layout, content, geometry, textures, decor, Sites, trees, maps, quality, pipeline, versions, export | `layout.py` 4643, `decor/placement.py` 2532, `geometry.py` 2147, `topology/embed.py` 2068 |
| `rules/` | data the generator reads, checked on load: `topology/`, `walls/`, `rooms/`, `sites/`, `decor/` | `decor/catalogue.json` (4,651 stock models) |
| `styles/` | measured style profiles per theme and biome | `dungeon.json` (10 zones), `cave.json` (8), `city.json` (6) |
| `server/` | the FastAPI app: generate, rebuild, edit, versions, room decor, export, version | `app.py` 1967 |
| `web/` | the browser app (TypeScript, Three.js) | `src/main.ts` 1436, `roomview.ts` 768, `api.ts` 698 |
| `scripts/` | stock surveys, sweeps, stage runner, worktree helpers, `task_status.py` | 31 scripts |
| `tests/` | pytest + Hypothesis, in tiers (quick, full, gate) | — |

## North-star rules (from `.kiro/steering/project.md`)

These bind every pillar.

1. **Indistinguishable from a hand-crafted zone**: natural geometry over clean architecture.
2. **Classic–PoP look by default.** That era ships as `.s3d`/WLD; we read both and write `.eqg`.
3. **Navigable**: every room reachable by an EQ-scale player (slope ≤ 40°, step ≤ 3 u), proven on the mesh.
4. **No manual modelling**: everything comes from prompts and parameters (stock Props copied from the user's own install are the one refinement, umbrella decision 31).
5. **No API by default**: rule planner and procedural textures need no keys or network.
6. **Randomness is a feature**: a fresh seed per generate unless pinned; a pinned seed reproduces.
7. **Under about 5 minutes per generate.**
8. **Suggestions stay suggestions**: pacing, gates, POIs and hints ride in the sidecar, never in geometry or collision.
9. **Z is up**, as in EverQuest; the web camera is set to match.
10. **The tool writes only under `output/`**; installing into the client is the user's manual step.

## Where to read more

- Pillars and their balance: [`docs/pillars/README.md`](pillars/README.md)
- Everything still open: [`OPEN.md`](../OPEN.md)
- Format gotchas and hard-won lessons: [`.kiro/steering/lessons-learned.md`](../.kiro/steering/lessons-learned.md)
- Authoring guides: [`docs/TOPOLOGY_RULES.md`](TOPOLOGY_RULES.md), [`docs/DECOR_RULES.md`](DECOR_RULES.md)
- Research verdicts: [`docs/RESEARCH.md`](RESEARCH.md)
- The original target design (partly stale, see each pillar's DESIGN): [`.kiro/specs/zone-generator/design.md`](../.kiro/specs/zone-generator/design.md)
