# Requirements Document

## Introduction

`zone-generator-wilderness` specifies the open-world wilderness zone generator
for the eq_s3d project — **roadmap step 1 of the 11-step content sequence**
(`ROADMAP.md`). Its outcome is a believable, walkable, sealed, eroded **open
Karana**: a procedural outdoor landscape for the RoF2 client, driven by a
natural-language prompt and viewable in the browser preview.

This is a **feature** spec that produces geometry. Step 1 is deliberately
**terrain-first**: the deliverable is **the land itself** — a heightfield carved
by erosion, ringed by an impassable rim (the bowl), broken only at declared zone
exits. The first biome is **plains (the Karanas)**. Named POIs/landmarks (huts,
camps, shrines) are **roadmap step 10**, not step 1; biomes beyond plains, real
water collision, interior-crossing rivers, and the architecture runway are all
out of the first cut (see *Out of scope*).

### Why this spec exists (design history)

An earlier wilderness attempt draped a heightfield under the **same TinyKeep
room-and-corridor layout** the dungeon backend uses: rooms became flat pads and
corridors became graded trails. That was rejected — wilderness must be a true
open landscape, not a room-graph in a grass skin. That drape work was cut; only
the `GeometryBackend` registry seam was kept on master. In M1 wilderness ships
**present-but-DISABLED**. This generator is the milestone that makes wilderness
real.

### Scope change from the lean v1 (terrain-first, Karana-first)

An earlier cut of this spec was **landmark-first** (desert+oasis,
plains+river-fork — a zone organized around a central landmark). That framing is
**superseded** (user decision, locked):

- **Terrain-first, not landmark-first.** The terrain (heightfield + erosion +
  the bowl) is the deliverable. Named POIs/landmarks move to roadmap step 10.
- **Plains (Karanas) is the lead biome.** The desert+oasis / plains+river-fork
  pairing is dropped as the organizing idea; biomes remain data-driven texture
  kits, but the first biome is `plains`.
- **The Design_Matrix IR and graph-replacement are KEPT**, but they now shape
  **terrain regions** (plains / river / cliff / mountain-rim / lava /
  zoneline-gap), not an oasis-first layout.
- **Erosion/deformation is now first-class** (was deferred): the heightfield is
  carved so valleys and ridgelines read as water-and-weather-made.
- **The bowl is first-class**: every EQ zone is a closed bowl — a playable
  interior ringed by an impassable rim, broken only at declared zone exits.

### Roadmap position and the dispersed architecture runway

This spec is **STEP 1** of the 11-step content sequence. The architecture runway
that was `zone-generator-followup` is **dispersed into later steps**, not a
prerequisite of step 1:

- The pluggable **`LayoutEngine` seam** lands with **step 6** (graph-replacement
  dungeon gen).
- The **3D `Envelope` + gate-learns-connectors** (staircase/bridge) land with
  **step 5/7** (outdoor dungeon carved into terrain; multi-level verticality).

Step 1 therefore MUST NOT invent or depend on those seams. It reuses the
project's existing terrain core (`generators/field/terrain.py`), the existing
`GeometryBackend`/`TerrainBackend` registry (`generators/backends.py`), the
existing `RegionSpec` machinery (`generators/zone_spec.py`,
`generators/builder.py`), and the existing planner seam (`ai/planner.py`).

## Glossary

- **Wilderness_Generator**: The system this spec defines — the terrain-first
  open-world wilderness zone generator (roadmap step 1).
- **Biome**: A data-driven KIT (ground-texture set, water presence,
  skybox/fog tint, vegetation kit) applied over one shared terrain core. The v1
  lead biome is `plains` (the Karanas); further biomes are fast-follow.
- **Design_Matrix**: The 2D intermediate IR — a grid of cells, each carrying a
  typed **Node_Type** plus an **Intent_Tag**. It governs **terrain regions**,
  not a landmark layout.
- **Node_Type**: The typed role of a Design_Matrix cell: one of
  `plains | river | cliff | mountain_rim | lava | zoneline_gap | water`
  (v1 set; extensible).
- **Intent_Tag**: Per-cell play intent: `playable` or `scenic`.
- **Playable_Region**: A maximal connected set of `playable` cells. Playable
  regions must be mutually reachable from Spawn.
- **Scenic_Region**: A set of `scenic` / backdrop cells that MAY be
  deliberately unreachable (e.g. the rim, distant mountains).
- **Graph_Replacement**: The rewrite pass that iterates on the Design_Matrix,
  applying rules that spawn/transform terrain nodes. Rules must terminate and
  preserve playable-reachability by construction.
- **Noise_Pass**: The noise synthesis that turns the Design_Matrix into a base
  heightfield. Subordinate to the matrix: masked from frozen cells, blended at
  edges.
- **Erosion** / **Deformation**: The first-class pass that carves the base
  heightfield with **hydraulic** (flow-accumulation) + **thermal** (talus
  relaxation) erosion so valleys and ridgelines read as water-and-weather-made.
  Must be vectorised (no per-voxel Python loop). Approximated-but-real for v1;
  full per-droplet simulation is a fast-follow.
- **Frozen_Cell**: A Design_Matrix cell whose terrain is constraint-governed
  (e.g. river channel, zoneline-gap floor, rim ridge target) and therefore
  masked out of the Noise_Pass.
- **Bowl**: The topological truth of every EQ zone — a playable interior fully
  enclosed by an impassable **Rim**, broken only at **Zoneline** gaps. The bowl
  is a COLLISION/TOPOLOGY property, not necessarily a visual one.
- **Rim**: The impassable perimeter boundary of the zone. Realized per
  **Edge_Connection**. An undeclared rim edge defaults to impassable mountain.
- **Edge_Connection**: A user-declared segment of the Rim with a typed behavior.
  The data model supports N perimeter segments; the four sides (N/E/S/W) are the
  simple default. v1 connection types: `river`, `mountain`, `zoneline`.
- **Zoneline**: An **open** Edge_Connection — a flat walkable GAP in the Rim
  leading off-map; the deliberate leak where an adjacent zone connects.
- **Lava**: An **interior** impassable + damaging hazard region (Lavastorm /
  Nagafen). Impassable geometry/barrier, flagged **damaging** in the sidecar for
  later runtime use. **Not** a v1 Rim/Edge_Connection type.
- **Water_Level**: The fixed Z height of the visual water plane for a zone. Water
  is **visual-only** in v1 (no collision volumes).
- **POI_Anchor**: A named point of interest (in step 1, primarily the Spawn and
  a small number of spawn clearings). Named landmarks/POIs are roadmap step 10.
- **Spawn**: The POI_Anchor a player starts at; the root of the reachability
  check.
- **Invisible_Wall**: A first-class authored barrier (an EQ convention) recorded
  in the sidecar as region metadata and later exportable as an EQ region record.
  Used to seal a `river` edge (which has no water collision) so the Rim does not
  leak.
- **Human_3D_Pass**: The manual acceptance review in `docs/ACCEPTANCE.md`.
  Required for every requirement that produces geometry, because structural
  tests passing is necessary but NOT sufficient in this project.
- **ZoneSpec**: The project's intermediate representation
  (`generators/zone_spec.py`) that everything flows through.

## Requirements

### Requirement 1: Prompt to plains-Karana terrain intent

**User Story:** As a user, I want to describe an open wilderness zone in natural
language, so that the generator produces a plains/Karana terrain without manual
modelling.

#### Acceptance Criteria

1. WHEN a prompt naming an open plains or Karana wilderness is submitted, THE Wilderness_Generator SHALL resolve it to the `plains` Biome.
2. WHERE no API key is configured, THE Wilderness_Generator SHALL resolve the Biome using the procedural rule planner without requiring any external service.
3. WHERE an LLM planner is configured, THE Wilderness_Generator SHALL accept an LLM-proposed Biome through the existing planner drop-in seam.
4. IF a prompt names a biome outside the v1 set, THEN THE Wilderness_Generator SHALL fall back to the `plains` Biome and record the substitution in the zone sidecar.
5. WHEN a Biome is resolved, THE Wilderness_Generator SHALL record the resolved biome on the ZoneSpec.

### Requirement 2: Design Matrix as the governing 2D terrain IR

**User Story:** As a developer, I want a 2D Design Matrix as the intermediate representation between intent and geometry, so that the terrain layout is inspectable and property-testable before any geometry exists.

#### Acceptance Criteria

1. WHEN a Biome is resolved, THE Wilderness_Generator SHALL construct a Design_Matrix of typed terrain cells covering the zone footprint.
2. THE Wilderness_Generator SHALL assign each Design_Matrix cell exactly one Node_Type from the v1 set (`plains | river | cliff | mountain_rim | lava | zoneline_gap | water`).
3. THE Wilderness_Generator SHALL assign each Design_Matrix cell exactly one Intent_Tag (`playable` or `scenic`).
4. WHEN the Design_Matrix is constructed, THE Wilderness_Generator SHALL lead the interior with `plains` cells and derive the terrain regions (river / cliff / lava / water) within that plains interior.
5. THE Wilderness_Generator SHALL expose the finished Design_Matrix for inspection before the Noise_Pass runs.
6. WHEN the Design_Matrix is constructed, THE Wilderness_Generator SHALL tag every perimeter cell as part of the Rim according to its Edge_Connection (Requirement 3).
7. WHEN any Design_Matrix contains `water` cells, THE Wilderness_Generator SHALL produce `water` cells that form a single connected region.

### Requirement 3: The Bowl via declared Edge Connections

**User Story:** As a designer, I want to declare how each side of the zone perimeter behaves, so that the zone is a sealed bowl broken only where I declare a zone exit.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL model the Rim as a user-declared set of N Edge_Connection segments around the zone perimeter.
2. WHERE the user declares the simple default, THE Wilderness_Generator SHALL use four Edge_Connection segments, one per side (North, East, South, West).
3. WHERE a perimeter edge has no declared Edge_Connection, THE Wilderness_Generator SHALL default that edge to an impassable `mountain` Rim.
4. WHERE an Edge_Connection is declared `mountain`, THE Wilderness_Generator SHALL raise that edge to a slope steeper than the traversability agent's climb cap so that the geometry itself seals the edge.
5. WHERE an Edge_Connection is declared `river`, THE Wilderness_Generator SHALL place a boundary-hugging visual water edge AND back that edge with an Invisible_Wall region that seals the edge, requiring no water collision.
6. WHERE an Edge_Connection is declared `zoneline`, THE Wilderness_Generator SHALL produce a flat walkable gap in the Rim that leads off-map.
7. THE Wilderness_Generator SHALL record every Edge_Connection type and every Invisible_Wall barrier in the `.zone.json` sidecar as region metadata suitable for later export as region records.

### Requirement 4: The Bowl Invariant — sealed rim, reachable interior (gate-enforced)

**User Story:** As a player, I want the playable interior fully reachable and the rim impassable everywhere except zone exits, so that the zone plays like a real EQ bowl and does not leak through the mountains.

> This requirement **AMENDS/EXTENDS** the prior reachability amendment. The gate
> no longer only proves playable reachability; it also proves the Rim is sealed.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL treat mutual reachability from Spawn as a required invariant for Playable_Regions, and SHALL exclude Scenic_Regions from that requirement.
2. WHEN a wilderness zone is built, THE Wilderness_Generator SHALL prove on the built mesh that every Playable_Region cell is reachable from Spawn by the project traversability agent.
3. WHEN a wilderness zone is built, THE Wilderness_Generator SHALL prove on the built mesh that no path from Spawn crosses the Rim except through a `zoneline` Edge_Connection segment.
4. IF a path from Spawn crosses a non-`zoneline` Rim segment, THEN THE Wilderness_Generator SHALL report a bowl-leak failure identifying the breached Rim segment.
5. WHEN a `zoneline` Edge_Connection is built, THE Wilderness_Generator SHALL produce a walkable gap that is reachable from Spawn and leads off-map.
6. IF a Playable_Region cell is not reachable from Spawn on the built mesh, THEN THE Wilderness_Generator SHALL report a reachability failure identifying the stranded region.

### Requirement 5: Erosion/deformation is first-class, vectorised, and rim-respecting

**User Story:** As a user, I want the terrain carved by erosion so valleys and ridgelines read as water-and-weather-made, so that the land looks eroded rather than noise-blobby — without breaching the bowl.

#### Acceptance Criteria

1. WHEN the base heightfield is synthesized, THE Wilderness_Generator SHALL carve it with a hydraulic erosion pass (flow accumulation) and a thermal erosion pass (talus relaxation).
2. THE Wilderness_Generator SHALL implement every erosion and deformation pass as vectorised numpy array operations without any per-voxel Python loop.
3. THE Wilderness_Generator SHALL complete the erosion passes within the five-minute generation budget (Requirement 13.3).
4. WHEN each noise, erosion, or deformation pass completes, THE Wilderness_Generator SHALL re-assert every non-`zoneline` Rim cell as impassable so that no pass breaches the Rim.
5. IF an erosion or deformation pass would carve a passable gully through a non-`zoneline` Rim segment, THEN THE Wilderness_Generator SHALL re-clamp that segment to impassable after the pass, preserving the bowl.

### Requirement 6: Visual softness — open interior, rim as distant backdrop

**User Story:** As a player, I want the interior to feel open, so that the rim reads as a distant backdrop I rarely bump into rather than a claustrophobic crater wall at the edge of play.

#### Acceptance Criteria

1. WHEN a wilderness zone is built, THE Wilderness_Generator SHALL keep the playable interior flat enough and wide enough that the Rim lies beyond the normal roaming area.
2. THE Wilderness_Generator SHALL keep the transition from the playable interior to the Rim set back from the interior by a stated margin so that the Rim is not adjacent to the play edge.
3. WHEN the Noise_Pass and erosion passes run over the playable interior, THE Wilderness_Generator SHALL keep interior slopes within the traversability agent's slope cap (Requirement 12.4).

### Requirement 7: Graph-replacement rules over terrain regions (terminate; preserve the bowl)

**User Story:** As a developer, I want the Design Matrix refined by graph-replacement rules that cannot loop, strand playable regions, or breach the rim, so that iterating the matrix is safe and deterministic.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL refine the Design_Matrix by applying Graph_Replacement rules over the terrain Node_Type vocabulary.
2. WHEN Graph_Replacement runs, THE Wilderness_Generator SHALL terminate within a bounded number of rewrite iterations.
3. WHILE Graph_Replacement is applying rules, THE Wilderness_Generator SHALL preserve mutual reachability among Playable_Regions at every committed rewrite step.
4. WHILE Graph_Replacement is applying rules, THE Wilderness_Generator SHALL preserve the Rim as impassable on every non-`zoneline` segment at every committed rewrite step.
5. WHEN a `cliff` node would strand a `playable` region, THE Wilderness_Generator SHALL apply a rule that spawns a graded approach restoring a playable approach to that region.
6. IF a Graph_Replacement rule would strand a `playable` region or breach a non-`zoneline` Rim segment, THEN THE Wilderness_Generator SHALL reject that rule application and preserve the prior matrix state.

### Requirement 8: Noise pass subordinate to the matrix

**User Story:** As a developer, I want the heightfield synthesized by a noise pass subordinate to the Design Matrix, so that hills decorate the landscape without pushing through rivers or flooding the rim gaps.

#### Acceptance Criteria

1. WHEN the Design_Matrix is finalized, THE Wilderness_Generator SHALL synthesize the base heightfield with a vectorised value-noise FBM pass before the erosion passes.
2. THE Wilderness_Generator SHALL mask the Noise_Pass out of every Frozen_Cell so that constraint-governed terrain is not altered by noise.
3. WHEN the Noise_Pass writes terrain adjacent to a Frozen_Cell, THE Wilderness_Generator SHALL blend the noise toward the frozen value at the shared edge.
4. THE Wilderness_Generator SHALL keep every `zoneline_gap` cell flat to within a stated flatness tolerance after the Noise_Pass completes.
5. THE Wilderness_Generator SHALL keep every `river` channel cell at or below its adjacent bank height after the Noise_Pass completes, so that terrain does not rise through the river.

### Requirement 9: Matrix-to-terrain upsample preserving sharp transitions

**User Story:** As a developer, I want the coarse Design Matrix upsampled to terrain resolution in a way that preserves sharp cliff, rim, and water edges, so that the landscape does not read as blocky or stair-stepped.

#### Acceptance Criteria

1. WHEN the Design_Matrix is upsampled to terrain resolution, THE Wilderness_Generator SHALL interpolate height smoothly across `plains`-to-`plains` cell boundaries.
2. WHEN the Design_Matrix is upsampled across a boundary between a `cliff` or `mountain_rim` cell and a non-`cliff`/non-`mountain_rim` cell, THE Wilderness_Generator SHALL preserve the height discontinuity as a sharp transition rather than smoothing it away.
3. WHEN the Design_Matrix is upsampled across a boundary between a `water` cell and a non-`water` cell, THE Wilderness_Generator SHALL preserve the shoreline as a sharp transition.
4. THE Wilderness_Generator SHALL produce upsampled cliff, rim, and shoreline edges that are free of axis-aligned stair-step artifacts introduced by the matrix grid.

### Requirement 10: Interior lava as an impassable, damaging hazard

**User Story:** As a designer, I want to place lava inside the zone as an impassable, damaging hazard, so that a Lavastorm/Nagafen-style region can seal a sub-region without being a rim type.

#### Acceptance Criteria

1. WHERE the Design_Matrix contains `lava` cells, THE Wilderness_Generator SHALL treat the lava region as impassable interior terrain.
2. THE Wilderness_Generator SHALL record every `lava` region in the `.zone.json` sidecar flagged as damaging for later runtime use.
3. THE Wilderness_Generator SHALL treat a `lava` region as an interior hazard only and SHALL NOT offer `lava` as an Edge_Connection type in v1.
4. WHERE a `lava` region separates a `playable` region from Spawn, THE Wilderness_Generator SHALL preserve a playable approach around the lava so that no `playable` region is stranded by lava.

### Requirement 11: Biome as a data-driven kit over the terrain core

**User Story:** As a user, I want the plains biome's identity carried mostly by ground texture, skybox/fog tint, and vegetation presence, so that the Karanas read as an EQ outdoor zone over the shared terrain engine.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL represent each Biome as a data-driven kit comprising a ground-texture set, a water-presence flag, a skybox/fog tint, and a vegetation-kit identity.
2. THE Wilderness_Generator SHALL apply the Biome over the one shared terrain core rather than a separate generator per biome.
3. WHEN the `plains` Biome is applied, THE Wilderness_Generator SHALL select the plains ground-texture set, skybox/fog tint, and vegetation-kit identity from biome data.
4. WHERE a Biome kit declares water present, THE Wilderness_Generator SHALL place the visual water plane for that zone.

### Requirement 12: Open-ground walkability of the playable interior

**User Story:** As a player, I want the playable ground of a wilderness zone to be walkable, so that I can traverse the whole interior without hitting ungraded cliffs or pits.

#### Acceptance Criteria

1. WHEN a wilderness zone is built, THE Wilderness_Generator SHALL produce playable ground on which every Playable_Region POI_Anchor is reachable from Spawn by the project traversability agent.
2. IF a Playable_Region POI_Anchor is not reachable from Spawn on the built mesh, THEN THE Wilderness_Generator SHALL report a walkability failure identifying that POI_Anchor.
3. WHILE enforcing walkability, THE Wilderness_Generator SHALL exclude Scenic_Regions (including the Rim) from the reachability requirement.
4. WHEN playable ground undulates, THE Wilderness_Generator SHALL keep walkable interior slopes within the project traversability agent's slope cap.

### Requirement 13: Visual-only water, randomness, performance, and the 3D gate

**User Story:** As a user, I want visual-only water, a fresh landscape each time within a reasonable time budget, and geometry-producing changes eyeballed in 3D, so that output stays correct, varied, and timely.

#### Acceptance Criteria

1. WHERE a zone contains `water` cells, THE Wilderness_Generator SHALL place a flat visual water plane at the Water_Level with the biome water material and SHALL NOT create water collision volumes in v1.
2. WHEN a wilderness zone is generated without a pinned seed, THE Wilderness_Generator SHALL draw a fresh seed so that repeated generation from the same prompt yields different landscapes.
3. WHEN a seed is pinned, THE Wilderness_Generator SHALL reproduce the same landscape for the same prompt and seed, and SHALL complete generation within five minutes.
4. THE Wilderness_Generator SHALL treat a passing structural and property test suite as necessary but not sufficient, requiring a Human_3D_Pass per `docs/ACCEPTANCE.md` for every geometry-producing change before that change is accepted.

### Requirement 14: EQG output, Z-up, and ZoneSpec flow

**User Story:** As a developer, I want the wilderness zone written as EQG with Z up and flowed through the existing ZoneSpec, so that it loads in the RoF2 client and the browser preview like every other zone.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL flow the Design_Matrix, heightfield, water plane, Edge_Connections, POI_Anchors, and biome kit through the ZoneSpec intermediate representation.
2. THE Wilderness_Generator SHALL write the wilderness zone in the EQG format currently produced by the project.
3. THE Wilderness_Generator SHALL emit geometry with Z as the up axis (the EverQuest convention).
4. THE Wilderness_Generator SHALL carry Intent_Tags, Edge_Connection types, POI_Anchor names, Invisible_Wall barriers, and the biome kit identity in the `.zone.json` sidecar rather than in the binary geometry.

## Out of scope (fast-follow — explicitly not in the first cut)

Named so step 1 stays bounded. These build on the same step-1 core and are
scoped here, not implemented in this cut:

- **Named wilderness POIs / landmarks** — huts, camps, shrines, oases as
  designed places. This is **roadmap step 10** (interesting wilderness POIs),
  not step 1.
- **Interior-crossing rivers** — South-Karana-style rivers that cross the
  interior rather than hugging a boundary edge (a named fast-follow deferral).
- **Real water collision volumes** — walkable-shallows and swimmable-deep
  volumes. v1 water is visual-only (Requirement 13.1); edges seal via the
  Invisible_Wall pattern, not water collision.
- **Full droplet-simulation erosion** — per-droplet hydraulic simulation
  replacing the flow-accumulation + thermal approximation, behind the same
  erosion interface. v1 ships approximated-but-real erosion.
- **Fast-follow biomes** — `desert`, `forest`, `coast`, `tundra` and their kits.
- **The dispersed architecture runway** — the pluggable `LayoutEngine` seam
  (roadmap step 6), the 3D `Envelope`, and the gate-learns-connectors work
  (roadmap steps 5/7). Step 1 reuses the existing terrain core and backend
  registry and does not stand these up.
- **Region-record export** — Invisible_Wall and lava barriers are recorded in
  the sidecar (Requirements 3.7, 10.2, 14.4); exporting them as live EQEmu
  region records rides with the SQL-export capstone, not here.

## Sources

- `ROADMAP.md` — the authoritative 11-step content sequence (this spec is
  **step 1 — Wilderness (Karanas): open heightfield with water, lava, cliffs and
  deformation**); the note that the `zone-generator-followup` runway is
  dispersed into steps 5/6/7; M1 ships wilderness present-but-disabled; the
  `GeometryBackend` registry seam kept on master; the earlier
  heightfield-under-TinyKeep drape that was rejected and cut.
- `.kiro/steering/lessons-learned.md` — "structural tests pass is necessary but
  NOT sufficient; eyeball it in 3D"; Z is up; EQG written and EQG collision is
  per-triangle; value-noise over opensimplex and **no per-voxel Python loops**;
  the "re-clamp / re-assert the invariant after every blend/pass" discipline.
- `generators/field/terrain.py` — the existing vectorised FBM + thermal-erosion
  + `_enforce_walkable` terrain core this step reuses and extends.
- `generators/backends.py` — the existing `GeometryBackend` / `TerrainBackend`
  registry wilderness routes through.
- `generators/zone_spec.py`, `generators/builder.py` — the existing `RegionSpec`
  machinery (region kinds `water`, `lava`→`ALV`, `zoneline`→`ATP`, generic) the
  Rim, lava, and Invisible_Wall records ride on, and the `.zone.json` sidecar.
- `ai/planner.py`, `ai/rule_planner.py` — the existing planner drop-in seam
  (rule planner default, LLM optional) used for biome resolution.
- `docs/ACCEPTANCE.md` — the Human_3D_Pass manual UAT checklist.
