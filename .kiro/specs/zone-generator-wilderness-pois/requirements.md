# Requirements Document

> **STATUS: roadmap step 10, draft.** Written 2026-11-07 at master `28b6781`. The design's
> open questions are waiting on the user (`design.md` "Open questions"); no task starts until
> they're answered. Task index: `tasks.md` (card format, 14 tasks).

## Introduction

Roadmap step 10: **interesting wilderness POIs: huts, camps, shrines.** A generated
wilderness today is ground, water, a rim and trees. It has a Spawn and nothing else to find.

Stock wilderness isn't empty. A probe of 14 Classic outdoor zones' placed objects (design
finding 1) shows trees outnumber everything, but every zone also has places: farmhouses, barns
and a corral in the Karanas, centaur lean-tos and burial mounds in South Karana, orc and goblin
tents round campfires in South Ro, igloos and halfling mounds in Everfrost, towers in the
deserts, an outpost and a shack in Qeynos Hills. In the Classic client these are **placed
objects**, not part of the terrain mesh, the same way trees are. Step 2 already builds
generated tree models and places them as ZON objects (umbrella decision 22), so this step
builds on that path rather than a new one.

This step puts **Sites** in wilderness and outdoor-dungeon zones: a camp, a hut, a farmstead,
a watchtower, a shrine, a ruin. Each Site is chosen by the biome and who lives there, stands on
ground flat enough to hold it, keeps every way through open, and names its points of interest
in the sidecar for the hand-finishing pass.

Earlier steps left these hooks:

- **`POIAnchor`** (`generators/wilderness/matrix.py`), which today carries only the Spawn.
- **Generated models as ZON objects** (step 2): `veg_<species>.mod`, one ZON object each,
  and a walk gate that keeps trunks from cutting the ground apart (`trees_block`).
- **Kept_Clear** ground (step 2): the Spawn clearing, zoneline approaches and shores.
- **Recipes and POIs as checked data** (step 9): `rules/rooms/`, with an advisory POI type.

This spec sits under the umbrella `zone-generator` (`.kiro/specs/zone-generator/`). "Req X.Y"
below means a requirement of THIS spec unless it says "umbrella".

**Out of step 10:** loose props and furnishing (crates, barrels, chairs, tables, haybales,
bedrolls: step 11); upper floors, ladders and platforms you climb (a tower here is solid);
roads and paths between Sites; NPC spawns, which belong to the SQL export (M6), so a POI only
names the spot; new biomes (only `plains` exists); real lights in the ZON; and the in-client
check (M6).

## Glossary

- **Site**: a designed place in the wilderness: a group of Structures on one patch of
  ground, with a kind, an Inhabitant and POIs.
- **Structure**: one generated model a Site is built from: a hut, tent, lean-to, tower,
  fire ring, fence run, standing stone, ruin wall. Placed as a ZON object, like a tree.
- **Enterable**: a Structure you can walk into (a hut, a lean-to, a ruin's ring): its walls
  are solid and it has an opening at least the clear width and head height.
- **Footprint**: a Structure's collidable triangles below head height, projected to the
  ground: what a player can't walk through.
- **Site_Recipe**: the data saying which Structures a Site kind has, how they're arranged
  (ring, row, cluster, lone, perimeter), how much ground it needs and what ground it likes.
- **Inhabitant**: who built a Site (human, orc, gnoll, centaur, ...). It weights which Site
  kinds appear and sets their materials and model variants.
- **Site_Clear**: ground around a Site that must stay walkable: its approach, the space
  around its openings, and a margin round its edge.
- **POI**: as step 9: a named point with a purpose ("camp fire", "hut interior", "shrine
  altar", "lookout"). Advisory: sidecar only.

## Requirements

### Requirement 1: Measure the stock Sites

**User Story:** As the project owner, I want stock wilderness places measured, so that how
many there are, how big, and where, come from real zones.

1. A survey SHALL group each Classic outdoor zone's placed objects into Sites (clusters of
   non-tree objects), and report per zone: Sites per 1e6 u² of walkable ground, Structures per
   Site, Site radius, nearest-neighbour spacing, distance to Spawn, zonelines and water, and the
   slope under each Site.
2. It SHALL measure each common Structure model (huts, tents, lean-tos, towers, fire rings,
   fences, monuments): triangle count, footprint, height, collidable share, and whether it
   can be walked into.
3. It SHALL say what it can't see: Sites built into the terrain mesh rather than placed, and
   objects it can't name.
4. The numbers SHALL set the bands of Req 9 and the densities of Req 5.

### Requirement 2: The gate knows Structures first

**User Story:** As a player, I want every Site to leave the zone walkable, so that no camp
walls me off.

1. Before any generator places a Structure, the walk gate SHALL judge hand-built zones holding
   Structures, from the models' own collidable triangles and not from the generator's record:
   a Footprint that cuts reached ground from Spawn, an Enterable Structure whose opening is
   narrower than the clear width or lower than head height, an Enterable interior not reached,
   and a POI not reached SHALL each fail, named.
2. The check SHALL replace step 2's trunk-disc check with the same rule for trees (a trunk
   is a Footprint), and SHALL give the same answer on every tree-only zone.

### Requirement 3: Structure models

**User Story:** As the project owner, I want Structures that read as Classic-era buildings,
so that a Site looks like it belongs.

1. Each Structure SHALL be a generated model (no mesh file read, umbrella Req 32.7), at the
   stock triangle counts of finding 1, closed where it's solid, origin at ground level, with
   a buried skirt so it shows no gap on uneven ground.
2. Collidable parts (walls, posts, stone) SHALL be solid; parts a player passes through
   (cloth flaps, smoke, thatch overhang above head height) SHALL carry `FLAG_PASSABLE`.
3. An Enterable Structure's floor SHALL be the ground under it; its opening SHALL be at least
   the clear width and head height.
4. Materials SHALL be procedural textures (timber, thatch, hide, canvas, stone), at the
   measured texel density.
5. Models SHALL round-trip through the `.mod` writer and reader exactly.

### Requirement 4: Placement keeps the zone open

**User Story:** As a player, I want Sites where a builder would put them, never in the way.

1. A Site SHALL stand only on playable plains, on ground no steeper than its recipe allows,
   outside Kept_Clear, and at least the recipe's spacing from every other Site.
2. Every Structure SHALL stand inside its Site's ground; its Site_Clear SHALL stay free of
   Structures and trees.
3. A Site or Structure that can't fit SHALL be dropped and recorded, never fail the build.
4. Placement SHALL draw from its own salted random stream, so terrain is identical whatever
   the Sites, and with Sites `none` trees are byte-identical to step 9.

### Requirement 5: Site recipes, as data

**User Story:** As the project owner, I want Sites described in data, so that new kinds and
Inhabitants don't need code.

1. Site_Recipes, Inhabitants and biome weights SHALL be TOML under `rules/sites/`, checked
   strictly on load, every bad value named by file, entry and field.
2. A recipe SHALL name its Structures, its arrangement, its ground (radius, slope, likes such
   as near water, high ground, by a zoneline) and its POIs.
3. Which Site kinds appear, and how often, SHALL come from Weights by biome and Inhabitant,
   set from finding 1.

### Requirement 6: POIs

1. Every Site SHALL name at least one POI; every POI SHALL stand on reached ground.
2. POIs SHALL ride in the sidecar only, and never change geometry.

### Requirement 7: Outdoor dungeons

1. Outdoor dungeons SHALL get Sites on their landscape, keeping the Apron, Tunnel and Mouth
   and the Host_Hill's footprint clear, and every step 5 guarantee SHALL hold.

### Requirement 8: Controls, sidecar and maps

1. A **Sites** control (None, Sparse, Normal, Dense; default Normal) and an **Inhabitants**
   control (the biome's mix, or one named Inhabitant) SHALL exist on the web page, the CLI and
   the plan; prompt words ("orc camp", "farmstead") SHALL choose them in the rule planner.
2. The sidecar SHALL list each Site: kind, Inhabitant, centre, Structures, POIs, and drops.
3. The EQ map SHALL draw each Structure's Footprint and a label at each Site; the web map SHALL
   show Sites.
4. Umbrella Req 32.4 SHALL be refined once more: landscape builds may pack generated Structure
   models (`site_<kind>.mod`), their textures, and one ZON object per Structure.

### Requirement 9: Like the stock zones, and everything else holds

1. Over many seeds at Normal, built zones SHALL measure inside the survey's bands for Sites
   per area, Structures per Site and spacing, with the survey's own code.
2. Dungeon and city builds SHALL be byte-identical; wilderness and outdoor-dungeon builds with
   Sites `none` SHALL be byte-identical to step 9. The gate's first-try rate SHALL hold.
3. The same inputs SHALL give byte-identical `.eqg` contents (footer aside).
4. A wilderness build SHALL take at most step 9's time plus 5 s.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge it, a step in
   `docs/ACCEPTANCE.md` "Step 10 — Wilderness POIs".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass: Sites read as what they are (a camp, a farm, a shrine),
   stand where someone would build them, look Classic-era, and never block the way.
