# Requirements Document

> **STATUS: roadmap step 2, DONE.** Written 2026-10-31; signed off 2026-11-01
> (master `8160b17`). The user answered the design's open questions on
> 2026-10-31 (`archive.md` "Decisions"). What landed: `archive.md`.

## Introduction

Roadmap step 2: **trees for wilderness.** Step 1 built the open Karana: an
eroded heightfield in a sealed bowl, with water, cliffs, lava and zone exits.
It has no trees, so it reads as bare ground. Step 2 dresses the playable land
with procedurally generated trees, so a wilderness build looks like a Karana
from the ground.

Measured on the stock client (`F:\everquest_rof2`, design "Research
findings"), the classic Karanas place 1,300–3,700 trees from 3–6 low-poly
species (31–40 triangles each). Placement is clustered into groves, not
uniform, and scale varies about 0.25×–2.25×. Each tree has a solid trunk and a
walk-through canopy. Step 2 copies that recipe at our zone size (2400 u
square, so roughly 100–250 trees).

This spec sits under the umbrella `zone-generator`
(`.kiro/specs/zone-generator/`) and builds on `zone-generator-wilderness`
(step 1). "Req X.Y" below means a requirement of THIS spec unless it says
"umbrella" or "wilderness".

**What it changes in the umbrella.** Umbrella Req 32.4 says builds contain no
`.mod` entries and no placeable objects. Step 2 refines it: a wilderness build
may contain generated vegetation models and their placements, and dungeon and
city builds still contain neither (Req 10). Umbrella Req 32.7 stands
unchanged: every tree mesh is generated from parameters, and no stock or
hand-made model is used.

**Out of step 2:** biomes beyond plains, bushes, grass tufts, rocks and other
props (step 10 POIs, step 11 decoration), trees in dungeons or cities, real
textures (steps 3–4; trees get the same procedural textures as the ground),
seasonal or animated foliage, LOD models, and trees on the EQ `.txt` map.

## Glossary

- **Vegetation_Kit**: the data entry, keyed by a biome's `vegetation_kit` id
  (`plains_grassland` for plains), listing the Species, their weights, the
  density per Density_Level and the grove parameters. Data, not code.
- **Species**: one tree form in a Vegetation_Kit (for plains: a broadleaf, a
  conifer and a sapling), with height and canopy ranges, trunk radius and
  base colours.
- **Tree_Model**: the `.mod` (EQGM) mesh generated for one Species: a Trunk
  and a Canopy.
- **Trunk**: the Tree_Model triangles that collide (polygon flag `0x01`
  clear).
- **Canopy**: the Tree_Model triangles that don't collide (flag `0x01` set),
  drawn with the alpha-tested (chroma) shader and a leaf texture with alpha.
- **Tree_Instance**: one placed tree: Species, world XY, Z, yaw and scale. It
  is written as one ZON object.
- **Density_Level**: `none`, `sparse`, `normal` (default) or `dense`.
- **Eligible_Ground**: the TER quads a tree may stand on (Req 4.1).
- **Trunk_Disc**: the XY disc of a Tree_Instance's trunk at ground level,
  radius = Species trunk radius × scale.
- **Tree_Clearance**: the minimum free gap between Trunk_Discs, and between a
  Trunk_Disc and a Kept_Clear area: 8 u, more than twice the player's width.
- **Kept_Clear**: areas no Trunk_Disc may touch: the Spawn clearing (radius
  120 u), each zoneline gap and its approach (the gap plus 2 fine cells
  inward), and a 1-fine-cell shore band beside water and river.
- **Grove_Ratio**: the median nearest-neighbour distance between
  Tree_Instances divided by the expected median for a uniform random scatter
  at the same density (`sqrt(ln 2 / (π · density))` ≈ `0.47 / sqrt(density)`).
  Below 1 means clustered.

## Requirements

### Requirement 1: Vegetation kit as data

**User Story:** As the project owner, I want each biome's trees described as
data, so that a new biome's trees are a data entry, not new code.

1. THE Vegetation_Kit for each biome SHALL be read from `styles/vegetation.json`
   by the biome's `vegetation_kit` id, and SHALL list at least one Species with
   a positive weight, a density (trees per 1,000,000 u²) for each Density_Level
   other than `none`, and grove parameters.
2. THE `plains_grassland` kit SHALL list 3 Species: a broadleaf, a conifer and a
   sapling, with heights in the measured Karana range (46–130 u at scale 1).
3. IF a biome's `vegetation_kit` id has no entry, THEN the build SHALL place no
   trees and record the warning `vegetation_kit_missing` naming the id.

### Requirement 2: Procedural tree models

**User Story:** As a zone author, I want low-poly trees in the Classic style,
so that the zone looks like the Karanas and not like a modern zone.

1. THE Tree_Model generator SHALL build one Tree_Model per Species as a pure
   function of the Species parameters and a seed, using no mesh file as input
   (umbrella Req 32.7).
2. Each Tree_Model SHALL have between 24 and 96 triangles.
3. Each Tree_Model SHALL have Trunk triangles with flag `0x01` clear and Canopy
   triangles with flag `0x01` set, and at least one of each.
4. THE Trunk SHALL extend from at least 2 u below the model origin up into the
   Canopy, so that a tree on a slope shows no gap under it (Req 5.3).
5. THE Canopy material SHALL use the chroma shader and a generated leaf texture
   whose alpha channel has both fully transparent and fully opaque texels; the
   Trunk material SHALL use the opaque shader and a generated bark texture.
6. Every Tree_Model SHALL re-read through `core.ter` as an `EQGM` file with
   identical vertices, triangles, flags and materials (round trip).

### Requirement 3: Density control

**User Story:** As a user, I want to ask for sparse plains or a dense wood, so
that I can steer how wooded the zone is.

1. A wilderness generate SHALL take a Density_Level from the controls
   (`controls.trees`), the CLI (`--trees`) or the prompt, in that order of
   precedence, defaulting to `normal`.
2. THE prompt planner SHALL map `treeless`/`barren`/`open` to `none`,
   `sparse`/`scattered` to `sparse`, and `forest`/`wooded`/`woods`/`dense` to
   `dense`, and record the chosen level and its source in the sidecar.
3. IF `trees` is given for a zone type other than wilderness, or with a value
   outside the four levels, THEN the server SHALL answer 400 naming `trees`, and
   the CLI SHALL exit 2, before any write.
4. THE Web_App Controls panel SHALL offer a Trees selector, shown only for
   wilderness, beside the Edges selectors.

### Requirement 4: Where trees may stand

**User Story:** As a player, I want trees only where trees make sense, so that
none stand in water, on cliffs or in the way of a zone exit.

1. Eligible_Ground SHALL be the TER quads whose two triangles are standable and
   at most 30° steep, whose fine cell's Node_Type is `plains`, which are not Rim
   seal cells, and which lie outside every Kept_Clear area.
2. EVERY Tree_Instance's Trunk_Disc SHALL lie wholly on Eligible_Ground.
3. EVERY pair of Tree_Instances SHALL have Trunk_Discs at least Tree_Clearance
   apart, and every Trunk_Disc SHALL be at least Tree_Clearance from all ground
   outside Eligible_Ground (Kept_Clear areas included).
4. WHEN the Density_Level is `none`, THE build SHALL place no Tree_Instance and
   pack no Tree_Model.

### Requirement 5: Placement that reads as hand-made

**User Story:** As a zone author, I want trees in groves with open meadows
between, so that the placement reads like a hand-dressed Karana, not a grid or
an even scatter.

1. THE placement SHALL be a pure function of the seed, the Rim declaration, the
   biome and the Density_Level.
2. FOR the `sparse`, `normal` and `dense` levels, on zones with at least 40
   Tree_Instances, the Grove_Ratio SHALL lie between 0.45 and 0.85 (the
   measured Karanas sit at 0.44–0.70 against their bounding-box area, a little
   higher against their playable area; design "Research findings").
3. EACH Tree_Instance's Z SHALL be the built terrain's surface height at its XY
   (sampled from the TER triangle under it), so that the Trunk's lowest point
   is at least 2 u below the surface at every point of the Trunk_Disc.
4. EACH Tree_Instance's yaw SHALL be drawn uniformly, and its scale SHALL lie in
   the Species' scale range (within 0.5–1.75 for plains).
5. THE placed density over Eligible_Ground SHALL be within ±25% of the kit's
   density for the chosen level, unless Eligible_Ground can't hold it under Req
   4.3, in which case the build SHALL record `vegetation_capped` with the placed
   and target counts.
6. THE share of Tree_Instances per Species SHALL be within ±15 percentage
   points of the kit weights, on zones with at least 40 Tree_Instances.

### Requirement 6: Trees keep the zone walkable

**User Story:** As a player, I want to reach every part of the zone I could
reach before trees were added, so that trees never wall off a meadow.

1. THE wilderness gate SHALL check that, with every Trunk_Disc grown by the
   player's half-width and removed, every playable cell is still reachable from
   Spawn, and every zoneline gap is still reachable from Spawn.
2. IF that check fails, THEN the build SHALL fail the gate with a reason naming
   a cut-off cell, so that the Pipeline retries with a fresh seed like any other
   gate failure.
3. THE placement SHALL be constructed so that the check in criterion 1 holds
   for every seed (a gate failure from trees is a bug, not an expected retry).

### Requirement 7: Terrain untouched

**User Story:** As the project owner, I want trees added on top of the terrain,
so that step 1's geometry, collision and maps don't move.

1. FOR every seed and Rim declaration, the TER bytes SHALL be identical at every
   Density_Level, including `none`.
2. THE outline, depth bands, map SVG outline layer and EQ map files SHALL be
   identical at every Density_Level (they are built from the TER alone, M2 Req
   1.1).

### Requirement 8: Archive and placement records

**User Story:** As a zone author, I want the trees in the `.eqg` the client
loads, so that they appear in game.

1. THE `.eqg` SHALL contain one `.mod` per Species with at least one
   Tree_Instance, named `veg_<species>.mod`, plus each Tree_Model material's
   textures.
2. THE `.zon` SHALL keep the TER as `models[0]`, list each packed Tree_Model
   once after it, and hold one object per Tree_Instance with a unique instance
   name, the Tree_Model's model index, position, yaw and scale.
3. THE Tier-1 format gate SHALL check that every ZON object's model index
   resolves to a packed `.mod` that re-reads through `core.ter`, that every
   material's textures are packed, and that every shader is one of the known
   shaders.

### Requirement 9: Preview and sidecar

**User Story:** As a user, I want to see the trees in the browser and know what
was placed, so that I can judge the zone before installing it.

1. THE GLB preview SHALL include every Tree_Instance as geometry in a node named
   `vegetation`, coloured by the Species' trunk and canopy base colours.
2. THE Web_App SHALL offer a toggle that hides and shows the `vegetation` node,
   reachable by keyboard.
3. THE sidecar SHALL carry a `vegetation` block: kit id, Density_Level and its
   source, count per Species, the Tree_Model filenames, the Grove_Ratio, and any
   `vegetation_capped` record.

### Requirement 10: Room-graph zones unchanged

**User Story:** As the project owner, I want dungeons and cities untouched by
this step.

1. Dungeon and city builds SHALL contain no `.mod` entries and no ZON objects
   (umbrella Req 32.4 as refined by step 2), and their EQG bytes SHALL be
   unchanged by this step for every seed.

### Requirement 11: Reproducible and quick

**User Story:** As a user, I want the same inputs to give the same trees, and
trees not to slow generation noticeably.

1. Two builds with the same seed, Rim declaration, biome, Density_Level and
   Build_Name SHALL produce byte-identical `.eqg` files (wilderness Property 16
   extended).
2. Vegetation (models, textures, placement and the walkability check) SHALL add
   at most 3 s to a `dense` wilderness build on the reference machine.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge it,
   a step in `docs/ACCEPTANCE.md` "Step 2 — Trees".
2. The fast and thorough suites are green.
3. The user signs off a human pass: trees read as Karana groves in the 3D view,
   stand on the ground, never block a zone exit, and the canopy is walk-through
   while the trunk is solid. The in-client check is M6 (as for maps).
