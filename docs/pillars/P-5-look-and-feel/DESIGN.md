# P-5 EverQuest look and feel — design (living)

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Checked against the code at master `c3d9b99` (2026-11-27, the commit that opened the project-docs spec). The lessons of the removed signed-distance-field
cave pipeline (voxel size 12, no decimation, floor clamping) are kept in
[lessons-learned "Geometry / fields"](../../../.kiro/steering/lessons-learned.md#geometry--fields)
for anyone who rebuilds natural geometry that way.

## Measured from stock

| What | Where | Used for |
|---|---|---|
| Style profiles | [`styles/dungeon.json`](../../../styles/dungeon.json) (10 zones), [`cave.json`](../../../styles/cave.json) (8), [`outdoor.json`](../../../styles/outdoor.json) (8), [`city.json`](../../../styles/city.json) (6) | geometry ranges, `fidelity.edge_median` (about 12–14 u), lighting, regions, `textures` (texel density per surface, and bands of measured texture statistics) |
| Biomes | [`styles/biomes.json`](../../../styles/biomes.json) (plains only) | wilderness ground layers by slope, height, moisture |
| Vegetation | [`styles/vegetation.json`](../../../styles/vegetation.json) (plains grassland: broadleaf, conifer, sapling) | tree kit |
| Surveys | `scripts/*_survey.py`, [`analyzer/style_builder.py`](../../../analyzer/style_builder.py) | room sizes per race (body height H), walls, tunnels, decor bands, Sites |

[`analyzer/inspect.py`](../../../analyzer/inspect.py) prints a zone's metrics against its profile. Light density reads 0 in
profiles because most stock dungeons are lit by light models placed in the zone, not ZON lights: accurate,
not a bug.

## Textures ([`generators/textures/`](../../../generators/textures))

- Material names are `<Texture_Set>_<Surface>` (`gnoll_temple_wall`, `wild_plains`,
  `liquid_water`); shader `Opaque_MaxCB1.fx`.
- Provider per surface (`factory.get_provider`): a room surface with a recipe
  ([`styles/texture_recipes.json`](../../../styles/texture_recipes.json)) gets the **recipe painter** (dressed stone, brick, flagstone,
  cobble, cave rock, planks, plaster, ice, sky); otherwise the **placeholder painter** (base colour,
  a pattern per surface class, the name in a 5×7 font). `EQ_S3D_TEXTURE_PROVIDER` = `procedural`
  or [`ai`](../../../ai) overrides. Trees and Structures have their own painters.
- Painters are tileable and pure; output is graded toward the theme's classic median and into
  the band between its 10th and 90th percentiles (`conformance.grade`). UVs repeat at the profile's texel density
  (`MaterialSpec.texel_density`), in EQ's Direct3D UV convention.
- Diffuse only: [`core/ter.py`](../../../core/ter.py) can write `e_TextureNormal0`, but nothing calls `add_normal`.
- The GLB preview carries each material's DDS and the TER's UVs.

## Walls ([`generators/wall_styles.py`](../../../generators/wall_styles.py), [`rules/walls/`](../../../rules/walls))

A Graph room keeps its Box and draws an **Outline** inside it from Cells: Voronoi for `rough`,
uneven-cornered facets for `hewn`, a grid for `built`. Walls are plumb; floors and ceilings move
but stay flat at each Throat. Corridors and textures follow their room's style. The style comes
from the room's Finish Scale (see P-7's design, "What a room holds"), which in a districted zone follows its District.
Classic-layout rooms stay rectangles.

## Winding and clumps

- A corridor with `rough > 0` winds along one centreline door to door (`CorridorSpec.path`)
  where its strip clears everything by a player's half-width, else per leg. Numbers from 113 stock
  tunnels: segments 20–72 u, turns up to 60°, wander 0.2.
- `ZonePlan.winding` (0–2) scales the wander; 0 is straight with square bends.
- Cave Graph rooms leave the lattice at any bearing; about a third of their level edges become
  **throats**: rooms 8 u wall to wall, doors in line.

## The `cave` Purpose

One of the 12 archetypes ([`generators/semantics.py`](../../../generators/semantics.py)). Room types `cave_mouth` (entrance),
`cavern` (hub), `grotto`, `flooded_gallery`, `sump`, `crystal_grotto` (climax), with `passage`,
`collapsed_gallery`, `warren`. Cold and crystal light; damp-rock palette; never lit warm, no
torches, chests or urns; rough walls on most Graph rooms; footprints from [`styles/cave.json`](../../../styles/cave.json) (a
size shift, ceilings kept). Prompt words for caves choose the Purpose, not the zone type.

## Water

A flooded room gets a flat, non-collidable `liquid_water` surface over its whole floor at
0.6 H, and its `AWT` region fills the room up to that line. The gate and decor skip non-solid
faces. Lava rooms still get a raised box region over 76% of the room ([P-5-5](OPEN.md#p-5-5)).

## Decor ([`generators/decor/`](../../../generators/decor), [`rules/decor/`](../../../rules/decor))

- **Catalogue**: every model in the install's 293 `_obj*.s3d` archives (4,651 models), in [`rules/decor/catalogue.json`](../../../rules/decor/catalogue.json),
  tagged by Category, kind, Mount, Set, era, collision, suits, condition; the user corrects tags in
  [`rules/decor/tags.toml`](../../../rules/decor/tags.toml). Vertex-animated models frozen; skeletal ones out.
- **Recipes** by tag: [`rules/decor/rooms.toml`](../../../rules/decor/rooms.toml) (by room type, kind, zone type, Site kind),
  [`rules/decor/sets.toml`](../../../rules/decor/sets.toml); layers in [`rules/decor/layers/`](../../../rules/decor/layers) ([`cave.toml`](../../../rules/decor/layers/cave.toml), [`tomb.toml`](../../../rules/decor/layers/tomb.toml)) merged base
  → theme → race → request ([`rules/decor/themes.toml`](../../../rules/decor/themes.toml)); a clash is refused unless the entry says `mode = "add"` or `"replace"`.
- **Placement** ([`generators/decor/placement.py`](../../../generators/decor/placement.py)) reads each room through a RoomContext ([`generators/room_context.py`](../../../generators/room_context.py);
  rooms, corridors except stairs and Bridges, Sites), the same way the gate does, inside stock
  bands of Props per room and Category shares. Its own `decor_seed`, and per-room seeds.
- **Pack**: used models are copied unchanged into the `.eqg` with one ZON object each and a ZON
  light at each light Prop's flame. Needs `EQ_PATH`; without it Decor falls back to none with a
  warning.
- **Room view** ([`generators/decor/room_view.py`](../../../generators/decor/room_view.py), `/api/room_decor`, [`web/src/roomview.ts`](../../../web/src/roomview.ts)): re-decorates one
  saved room with the rule files read fresh, same seed derivation as the build.

## Wilderness and trees

[`generators/wilderness/`](../../../generators/wilderness): a Design_Matrix of cells (plains, river, cliff, mountain rim, lava,
zoneline gap, water) grown by graph replacement, then noise subordinate to it, hydraulic and
thermal erosion, a sharp-edge upsample, and the **bowl**: mountain slope seal, invisible wall on
the river, zoneline gaps, interior lava. Every wilderness is 2400 u square, outdoor dungeons
1200 u. Trees ([`generators/vegetation/`](../../../generators/vegetation)): procedural `.mod` per species (solid trunk, passable
canopy), placed in groves on ground no steeper than 30°, clear of water, rim, Spawn and exits.
