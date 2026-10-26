# Requirements Document

## Introduction

`zone-generator-wilderness` specifies the open-world wilderness zone generator
for the eq_s3d project: a procedural generator that produces a genuinely **open,
scenic EverQuest outdoor landscape** (a forest by a river, an oasis in the
desert) for the RoF2 client, driven by a natural-language prompt and viewable in
the browser preview.

This is a **feature** spec that produces geometry. It is deliberately scoped
**lean for v1** — two biome+landmark pairs (desert+oasis, plains+river-fork) —
with the remaining biomes and landmarks named as explicit fast-follow work that
is **out of the first cut**.

### Why this spec exists (design history)

An earlier wilderness attempt draped a heightfield under the **same TinyKeep
room-and-corridor layout** the dungeon backend uses: rooms became flat pads and
corridors became graded trails. That was rejected — wilderness must be a true
open landscape, not a room-graph in a grass skin. That drape work was cut; only
the `GeometryBackend` registry seam was kept on master. In M1 wilderness ships
**present-but-DISABLED**. This generator is the post-M1 milestone that makes
wilderness real, built on a different layout architecture: **landmark-first,
landscape-around-a-landmark.**

### Ordering and dependency chain (post-M1, post-followup)

This is a **POST-M1, post-`zone-generator-followup` milestone.** It must not
begin until both land:

```
M1 (dungeon + city shipping; wilderness present-but-disabled)
  -> zone-generator-followup runway (F1 LayoutEngine seam, F2 3D Envelope +
     typed edges, F3 harness, F4 gate-learns-connectors)
    -> THIS spec (the wilderness engine)
```

This generator is a **`LayoutEngine` implementation (or a sibling layout stage)
behind followup's F1 seam** (`.kiro/specs/zone-generator-followup/requirements.md`
Req F1, `design.md` "The engine seam"). It **reuses** that seam, the
dimension-free **mission-grammar / graph-rewrite** layer, and the **`Envelope`**
concept (followup Req F2). It **MUST NOT** invent a parallel layout
architecture. Where this spec diverges from followup, it says so explicitly (see
Requirement 3, the reachability amendment).

## Glossary

- **Wilderness_Generator**: The system this spec defines — the open-world
  wilderness zone generator.
- **Biome**: A data-driven KIT (ground-texture set, water presence,
  skybox/fog tint, vegetation kit) applied over one shared terrain+hydrology
  core. v1 biomes: `desert`, `plains`.
- **Landmark**: The central geographic feature a wilderness zone is built
  around (e.g. an oasis, a river fork). The landmark and its supporting
  geography ARE the design; hills are context.
- **Landmark_Intent**: The biome + landmark pairing parsed from the prompt
  (e.g. "oasis in the desert" -> `desert` + `oasis`).
- **Design_Matrix**: The 2D intermediate IR — a biome/intent-tagged
  specialization of followup's `Envelope`. A grid of cells; each cell carries a
  typed **Node_Type** plus an **Intent_Tag**.
- **Node_Type**: The typed role of a Design_Matrix cell: one of
  `river | cliff | flatland | oasis | landmark_pad | water | backdrop` (v1 set;
  extensible).
- **Intent_Tag**: Per-cell play intent: `playable` or `scenic`.
- **Playable_Region**: A maximal connected set of `playable` cells. Playable
  regions must be mutually reachable from spawn.
- **Scenic_Region**: A set of `scenic` / backdrop cells that MAY be
  deliberately unreachable.
- **Graph_Replacement**: The rewrite pass that iterates on the Design_Matrix,
  applying rules that spawn/transform nodes (reuses followup's graph-rewrite
  layer). Rules must terminate and preserve playable-reachability by
  construction.
- **Noise_Pass**: The noise/erosion synthesis that turns the finished
  Design_Matrix into a heightfield. Subordinate to the matrix: masked from
  frozen cells, blended at edges.
- **Frozen_Cell**: A Design_Matrix cell whose terrain is constraint-governed
  (e.g. landmark pad, river channel) and therefore masked out of the Noise_Pass.
- **Water_Level**: The fixed Z height of the visual water plane for a zone.
- **POI_Anchor**: A named point of interest (the landmark plus a few camps /
  spawn clearings). Wilderness uses POI anchors instead of rooms.
- **Spawn**: The POI_Anchor a player starts at; the root of the reachability
  check.
- **Invisible_Wall**: A first-class authored barrier (an EQ convention) that
  makes a Scenic_Region unreachable without visible geometry; eventually
  exportable as a region record.
- **Envelope**: The bounded 3D layout volume from `zone-generator-followup`
  Req F2.
- **Human_3D_Pass**: The manual acceptance review in `docs/ACCEPTANCE.md`.
  Required for every requirement that produces geometry, because structural
  tests passing is necessary but NOT sufficient in this project.
- **ZoneSpec**: The project's intermediate representation
  (`generators/zone_spec.py`) that everything flows through.

## Requirements

### Requirement 1: Prompt to biome and landmark intent

**User Story:** As a user, I want to describe a wilderness zone in natural
language, so that the generator produces the biome and central landmark I asked
for without manual modelling.

#### Acceptance Criteria

1. WHEN a prompt naming a supported biome and landmark is submitted, THE Wilderness_Generator SHALL resolve it to a Landmark_Intent drawn from the v1 set (`desert`+`oasis`, `plains`+`river_fork`).
2. WHERE no API key is configured, THE Wilderness_Generator SHALL resolve the Landmark_Intent using the procedural rule planner without requiring any external service.
3. WHERE an LLM planner is configured, THE Wilderness_Generator SHALL accept an LLM-proposed Landmark_Intent through the existing planner drop-in seam.
4. IF a prompt names a biome or landmark outside the v1 set, THEN THE Wilderness_Generator SHALL fall back to the nearest supported Landmark_Intent and record the substitution in the zone sidecar.
5. WHEN a Landmark_Intent is resolved, THE Wilderness_Generator SHALL record the resolved biome and landmark on the ZoneSpec.

### Requirement 2: Design Matrix as the governing 2D IR

**User Story:** As a developer, I want a 2D Design Matrix as the intermediate representation between intent and geometry, so that the zone layout is inspectable and property-testable before any geometry exists.

#### Acceptance Criteria

1. WHEN a Landmark_Intent is resolved, THE Wilderness_Generator SHALL construct a Design_Matrix as a biome/intent-tagged specialization of the followup `Envelope`.
2. THE Wilderness_Generator SHALL assign each Design_Matrix cell exactly one Node_Type from the v1 set (`river | cliff | flatland | oasis | landmark_pad | water | backdrop`).
3. THE Wilderness_Generator SHALL assign each Design_Matrix cell exactly one Intent_Tag (`playable` or `scenic`).
4. WHEN the Design_Matrix is constructed, THE Wilderness_Generator SHALL place the Landmark node first and derive supporting geography around the Landmark node (landmark-first construction).
5. THE Wilderness_Generator SHALL expose the finished Design_Matrix for inspection before the Noise_Pass runs.
6. WHEN a desert+oasis Design_Matrix is constructed, THE Wilderness_Generator SHALL surround every `oasis` cell with `desert`-appropriate `flatland` or `backdrop` cells so that no `oasis` cell touches the matrix boundary.
7. WHEN any Design_Matrix is constructed, THE Wilderness_Generator SHALL produce `water` cells that form a single connected region.

### Requirement 3: Reachability amendment — playable-vs-scenic (amends followup)

**User Story:** As a designer, I want only the playable parts of a wilderness zone to be required reachable, so that cliffs, deep water, and backdrops can be deliberately unreachable the way real EQ outdoor zones are.

> This requirement **AMENDS** `zone-generator-followup`, whose gate assumes full
> walkable connectivity. For wilderness, full connectivity is NOT a global
> invariant.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL treat mutual reachability from Spawn as a required invariant for Playable_Regions only, not for the whole zone.
2. WHERE a region is tagged `scenic`, THE Wilderness_Generator SHALL permit that region to be unreachable from Spawn.
3. THE Wilderness_Generator SHALL realize deliberate unreachability of a Scenic_Region through cliffs, deep water, or Invisible_Wall barriers.
4. WHEN the Design_Matrix is constructed, THE Wilderness_Generator SHALL propose a default `playable`/`scenic` Intent_Tag for every region.
5. WHERE a user overrides the Intent_Tag of a region, THE Wilderness_Generator SHALL honor the override when enforcing the reachability invariant.
6. IF a region tagged `playable` is not reachable from Spawn, THEN THE Wilderness_Generator SHALL report a reachability failure identifying the stranded region.
7. IF the Landmark node is tagged `playable` and is not reachable from Spawn, THEN THE Wilderness_Generator SHALL report a reachability failure.

### Requirement 4: Graph-replacement rules (terminate; preserve reachability by construction)

**User Story:** As a developer, I want the Design Matrix refined by graph-replacement rules that cannot loop or strand playable regions, so that iterating the matrix is safe and deterministic.

> **Adversarial risk #3** (rewrite rules can loop / contradict / strand
> regions) is addressed here. Reuses the followup graph-rewrite layer and the
> solvability-invariant discipline the dungeon gating already uses.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL refine the Design_Matrix by applying Graph_Replacement rules that reuse the followup graph-rewrite layer rather than a parallel rewrite implementation.
2. WHEN Graph_Replacement runs, THE Wilderness_Generator SHALL terminate within a bounded number of rewrite iterations.
3. WHILE Graph_Replacement is applying rules, THE Wilderness_Generator SHALL preserve mutual reachability among Playable_Regions at every rewrite step.
4. WHEN a `cliff` node is present, THE Wilderness_Generator SHALL apply a rule that spawns ramp or pass nodes providing a playable approach to any `playable` region the cliff would otherwise strand.
5. WHEN a `river` node is present in a plains+river-fork zone, THE Wilderness_Generator SHALL apply a rule that grows the river into a fork.
6. IF a Graph_Replacement rule would strand a `playable` region, THEN THE Wilderness_Generator SHALL reject that rule application and preserve the prior matrix state.

### Requirement 5: Noise/erosion pass subordinate to the matrix

**User Story:** As a developer, I want the heightfield synthesized by a noise and erosion pass that is subordinate to the Design Matrix, so that hills decorate the landscape without pushing through rivers or tilting the landmark pad.

> **Adversarial risk #1** (the noise pass fights the matrix) is addressed here
> by freeze/mask discipline.

#### Acceptance Criteria

1. WHEN the Design_Matrix is finalized, THE Wilderness_Generator SHALL synthesize the heightfield with a Perlin-class noise pass plus a local erosion pass.
2. THE Wilderness_Generator SHALL mask the Noise_Pass out of every Frozen_Cell so that constraint-governed terrain is not altered by noise.
3. WHEN the Noise_Pass writes terrain adjacent to a Frozen_Cell, THE Wilderness_Generator SHALL blend the noise toward the frozen value at the shared edge.
4. THE Wilderness_Generator SHALL keep every `landmark_pad` cell flat to within a stated flatness tolerance after the Noise_Pass completes.
5. THE Wilderness_Generator SHALL keep every `river` channel cell at or below its adjacent bank height after the Noise_Pass completes, so that terrain does not rise through the river.

### Requirement 6: Matrix-to-terrain upsample preserving sharp transitions

**User Story:** As a developer, I want the coarse Design Matrix upsampled to terrain resolution in a way that preserves sharp cliff and water edges, so that the landscape does not read as blocky or stair-stepped.

> **Adversarial risk #2** (matrix resolution vs feature sharpness) is addressed
> here.

#### Acceptance Criteria

1. WHEN the Design_Matrix is upsampled to terrain resolution, THE Wilderness_Generator SHALL interpolate height smoothly across `flatland`-to-`flatland` cell boundaries.
2. WHEN the Design_Matrix is upsampled across a boundary between a `cliff` cell and a non-`cliff` cell, THE Wilderness_Generator SHALL preserve the height discontinuity as a sharp transition rather than smoothing it away.
3. WHEN the Design_Matrix is upsampled across a boundary between a `water` cell and a non-`water` cell, THE Wilderness_Generator SHALL preserve the shoreline as a sharp transition.
4. THE Wilderness_Generator SHALL produce upsampled cliff and shoreline edges that are free of axis-aligned stair-step artifacts introduced by the matrix grid.

### Requirement 7: Biomes as data-driven kits over one terrain core

**User Story:** As a user, I want the biome's identity carried mostly by ground texture, skybox/fog tint, and vegetation, so that desert and plains read as distinct EQ outdoor zones over one shared terrain engine.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL represent each Biome as a data-driven kit comprising a ground-texture set, a water-presence flag, a skybox/fog tint, and a vegetation kit.
2. THE Wilderness_Generator SHALL apply all v1 Biomes over one shared terrain-and-hydrology core rather than a separate generator per biome.
3. WHEN the `desert` Biome is applied, THE Wilderness_Generator SHALL select the desert ground-texture set, skybox/fog tint, and vegetation kit from biome data.
4. WHEN the `plains` Biome is applied, THE Wilderness_Generator SHALL select the plains ground-texture set, skybox/fog tint, and vegetation kit from biome data.
5. WHERE a Biome kit declares water present, THE Wilderness_Generator SHALL place the visual water plane for that zone.

### Requirement 8: Visual-only water plane (v1)

**User Story:** As a user, I want a flat water plane at a water level with a shoreline blend, so that oases and rivers read as water in v1 without the cost of real swimmable volumes.

#### Acceptance Criteria

1. WHERE a zone contains `water` or `oasis` cells, THE Wilderness_Generator SHALL place a flat visual water plane at the Water_Level.
2. THE Wilderness_Generator SHALL apply the biome water material to the water plane.
3. WHEN terrain meets the Water_Level, THE Wilderness_Generator SHALL blend the shoreline texture across the land-water boundary.
4. THE Wilderness_Generator SHALL mark real walkable-shallows and swimmable-deep water volumes as out of scope for v1 (deferred to a later version).

### Requirement 9: Approximate rivers-as-splines with local erosion (v1)

**User Story:** As a developer, I want rivers defined as splines with locally eroded banks, so that a river valley reads as water-made in v1 without full hydraulic simulation.

#### Acceptance Criteria

1. WHEN a zone contains a river, THE Wilderness_Generator SHALL define the river as a drainage spline that governs the valley.
2. WHEN the river spline is realized, THE Wilderness_Generator SHALL carve the channel along the spline and locally erode the banks so that the valley reads as water-made.
3. WHEN a plains+river-fork zone is generated, THE Wilderness_Generator SHALL realize a river fork as two spline branches meeting at a junction.
4. THE Wilderness_Generator SHALL expose the river/drainage behavior behind one interface so that a full hydraulic-erosion drainage-network simulation can replace the spline approximation later without changing callers.

### Requirement 10: Procedural-only texturing with AI drop-in seam preserved

**User Story:** As a user, I want procedural slope/height/moisture-blended textures that work with zero API keys, so that the generator stays usable by default while leaving the AI-texture upgrade available.

#### Acceptance Criteria

1. WHERE no API key is configured, THE Wilderness_Generator SHALL texture the terrain procedurally without requiring any external service.
2. THE Wilderness_Generator SHALL blend ground textures by surface slope, height, and moisture.
3. THE Wilderness_Generator SHALL route texture generation through the existing AI-texture drop-in seam so that an AI texture provider can be supplied without changing the generator.
4. WHEN a `water`-adjacent surface is textured, THE Wilderness_Generator SHALL raise the moisture input near the Water_Level so that shorelines read as damp ground.

### Requirement 11: POI anchors instead of rooms

**User Story:** As a designer, I want wilderness to use named POI anchors instead of a room graph, so that navigability is open-ground walkability around points of interest rather than room-to-room connectivity.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL represent points of interest as named POI_Anchors (the Landmark plus a small number of camps or spawn clearings) rather than as rooms.
2. THE Wilderness_Generator SHALL NOT use the TinyKeep room-and-corridor layout to lay out a wilderness zone.
3. WHEN POI_Anchors are placed, THE Wilderness_Generator SHALL designate one POI_Anchor as the Spawn.
4. THE Wilderness_Generator SHALL evaluate wilderness navigability as open-ground walkability among the POI_Anchors in Playable_Regions.

### Requirement 12: Open-ground walkability of playable regions

**User Story:** As a player, I want the playable ground of a wilderness zone to be walkable, so that I can traverse between every playable POI without hitting ungraded cliffs or pits.

#### Acceptance Criteria

1. WHEN a wilderness zone is built, THE Wilderness_Generator SHALL produce playable ground on which every Playable_Region POI_Anchor is reachable from Spawn by the project traversability agent.
2. IF a Playable_Region POI_Anchor is not reachable from Spawn on the built mesh, THEN THE Wilderness_Generator SHALL report a walkability failure identifying that POI_Anchor.
3. WHILE enforcing walkability, THE Wilderness_Generator SHALL exclude Scenic_Regions from the reachability requirement.
4. WHEN playable ground undulates, THE Wilderness_Generator SHALL keep walkable slopes within the project traversability agent's slope cap.

### Requirement 13: EQG output, Z-up, and ZoneSpec flow

**User Story:** As a developer, I want the wilderness zone written as EQG with Z up and flowed through the existing ZoneSpec, so that it loads in the RoF2 client and the browser preview like every other zone.

#### Acceptance Criteria

1. THE Wilderness_Generator SHALL flow the Design_Matrix, heightfield, water plane, POI_Anchors, and biome kit through the ZoneSpec intermediate representation.
2. THE Wilderness_Generator SHALL write the wilderness zone in the EQG format currently produced by the project.
3. THE Wilderness_Generator SHALL emit geometry with Z as the up axis (the EverQuest convention).
4. THE Wilderness_Generator SHALL carry Intent_Tags, POI_Anchor names, and the biome kit identity in the `.zone.json` sidecar rather than in the binary geometry.
5. WHERE Invisible_Wall barriers are placed, THE Wilderness_Generator SHALL record them as sidecar region metadata suitable for later export as region records.

### Requirement 14: Randomness, performance, and the 3D acceptance gate

**User Story:** As a user, I want a fresh landscape each time within a reasonable time budget, and I want geometry-producing changes eyeballed in 3D, so that output stays varied, timely, and actually correct.

#### Acceptance Criteria

1. WHEN a wilderness zone is generated without a pinned seed, THE Wilderness_Generator SHALL draw a fresh seed so that repeated generation from the same prompt yields different landscapes.
2. WHEN a seed is pinned, THE Wilderness_Generator SHALL reproduce the same landscape for the same prompt and seed.
3. WHEN a wilderness zone is generated, THE Wilderness_Generator SHALL complete generation within five minutes.
4. THE Wilderness_Generator SHALL treat a passing structural and property test suite as necessary but not sufficient, requiring a Human_3D_Pass per `docs/ACCEPTANCE.md` for every geometry-producing change before that change is accepted.

## Out of scope (fast-follow — explicitly not in the first cut)

Named so v1 stays bounded. These build on the same v1 core and are scoped here,
not implemented in this cut:

- **Fast-follow biomes:** `forest`, `coast`, `tundra`.
- **Fast-follow landmarks:** `temple`/`ruin`, `lake`, `mountain_pass`.
- **Real water volumes:** walkable-shallows and swimmable-deep volumes (v1 is a
  visual-only flat water plane — Requirement 8).
- **Full hydraulic erosion:** drainage-network simulation replacing the
  rivers-as-splines approximation, behind the same interface (Requirement 9.4).
- **AI textures by default:** the AI-texture seam is preserved (Requirement 10),
  but procedural textures remain the zero-key default.
- **Region-record export:** Invisible_Wall barriers are recorded in the sidecar
  (Requirement 13.5); exporting them as live EQEmu region records rides with the
  SQL-export capstone (umbrella M6), not here.

## Sources

- `.kiro/specs/zone-generator-followup/requirements.md` and `design.md` — the
  reused `LayoutEngine` seam (Req F1), typed edges + 3D `Envelope` (Req F2), the
  side-by-side harness (Req F3), the gate-learns-connectors discipline (Req F4),
  and the dimension-free mission-grammar / graph-rewrite layer this generator
  sits behind. This spec AMENDS followup's full-connectivity assumption (see
  Requirement 3).
- `ROADMAP.md` — M1 ships wilderness present-but-disabled; the `GeometryBackend`
  registry seam kept on master; the earlier heightfield-under-TinyKeep drape
  that was rejected and cut.
- `.kiro/steering/lessons-learned.md` — "structural tests pass is necessary but
  NOT sufficient; eyeball it in 3D"; Z is up; EQG collision is per-triangle;
  value-noise over opensimplex for performance.
- `docs/ACCEPTANCE.md` — the Human_3D_Pass manual UAT checklist.
