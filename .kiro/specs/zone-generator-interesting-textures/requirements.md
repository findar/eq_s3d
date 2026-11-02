# Requirements Document

> **STATUS: roadmap step 4, draft.** Written 2026-11-01. The design's open
> questions are waiting on the user (`design.md` "Open questions"). Task index:
> `tasks.md` (card format).

## Introduction

Roadmap step 4: **interesting textures, the real procedural texture pass.**
Step 3 named every material `<set>_<surface>` and drew it as a labelled
placeholder. Behind the placeholders, the procedural textures are tinted value
noise, and measured against the stock client they look nothing like Classic–PoP
zones (design "Research findings"):

- **Too smooth:** classic textures carry about four times the fine detail
  (median edge energy 0.028 against our 0.007).
- **Too pale and grey:** classic textures are darker (median luminance 0.23
  against our 0.41) and much more saturated (0.41 against 0.17).
- **Wrong scale:** classic dungeons repeat a 256×256 texture every ~14 u on
  walls (the per-zone wall median is 12–24 u in 11 of 16 classic zones
  measured; ~15 u overall) and 14–40 u on floors. We
  repeat every 100 u, so a texel covers seven times the ground.
- **No structure:** classic walls are stone blocks, bricks, timber and plaster,
  with joints and edges; ours have no shapes at all.

Step 4 measures the classic look into the style profiles, then generates
textures that match it: a recipe per material family (dressed stone, brick,
flagstone, cave rock, planks, plaster, dirt, grass, mud, lava, water…) with
structure, the measured palette and detail, at the measured texel density.

This spec sits under the umbrella `zone-generator`
(`.kiro/specs/zone-generator/`). "Req X.Y" below means a requirement of THIS
spec unless it says "umbrella".

**From the umbrella.** Umbrella Req 15 (era fidelity and measured conformance)
gains texture metrics. Umbrella Req 16 (procedural normal maps) is Open
question 2. Umbrella Req 26 (determinism) gains the procedural seed fix the
ROADMAP lists as a known issue.

**Out of step 4:** hand-painted or stock textures (umbrella Req 32.7 keeps
every asset generated), new materials or a new split of surfaces (step 8,
interesting room walls), decals and props (steps 10–11), animated water or
lava, an AI-texture overhaul (the AI provider stays an optional drop-in), and
the in-client check (M6).

## Glossary

- **Texture_Profile**: the measured texture data in a theme's style profile
  (`styles/<theme>.json` `textures` block): texel density per Surface
  (world units per repeat, p25/p50/p75) and look statistics (luminance mean
  and spread, saturation, edge energy; p10/p50/p90).
- **Texel_Density**: world units per texture repeat on a surface. Classic
  dungeon walls: ~14 u.
- **Texture_Family**: a recipe class a material is drawn with: `dressed_stone`,
  `brick`, `flagstone`, `cobble`, `cave_rock`, `planks`, `plaster`, `dirt`,
  `grass`, `mud`, `sand`, `lava`, `water`, `ice`, `sky`.
- **Texture_Recipe**: the data that maps a Material_Name (its Texture_Set and
  Surface, plus the theme) to a Texture_Family and its parameters (block size,
  joint width, palette jitter, roughness). Data, not code.
- **Look_Stats**: (luminance mean, luminance std, mean saturation, edge
  energy) of a 256×256 texture; edge energy is the mean absolute luminance
  step between neighbouring pixels.
- **Texture_Mode**: as in step 3: `procedural` (now the recipes),
  `placeholder` or `ai`.

## Requirements

### Requirement 1: Read classic UVs

**User Story:** As the project owner, I want the WLD reader to keep texture
coordinates, so that classic texel density can be measured, not guessed.

1. `core/wld.py` SHALL return each 0x36 mesh's texture coordinates (old
   format: 2 × int16 / 256; new: 2 × int32 / 256) and each polygon's texture
   index from the polygon-texture groups, alongside the existing vertices and
   polygons.
2. Existing callers SHALL see the same vertices, polygons and texture names
   as before.

### Requirement 2: Texture_Profile in the style profiles

**User Story:** As the project owner, I want the classic texture look
measured per theme, so that generated textures are judged against real zones.

1. The analyzer SHALL measure, over the theme's analysed zones, Texel_Density
   per Surface (wall, floor, ceiling; classified by face normal) and Look_Stats
   over every 256×256 texture, and SHALL write them as the theme's
   Texture_Profile.
2. The placeholder `uv.scale` block (always 1.0) SHALL be replaced by the
   measured Texel_Density.
3. Re-running the analyzer on the same install SHALL give the same profile.

### Requirement 3: Texture recipes

**User Story:** As a user, I want each surface drawn as what it is, so that a
temple wall looks like carved sandstone and a cave ceiling like rough rock.

1. Every Material_Name a build can produce SHALL resolve, through the
   Texture_Recipe data, to one Texture_Family and its parameters; a name with
   no entry SHALL fall back by Surface (wall → `dressed_stone`, floor →
   `flagstone`, ceiling → `cave_rock`, ground → `dirt`) and be recorded in the
   sidecar.
2. Themes SHALL differ: the same Surface under two archetypes or tints SHALL
   resolve to different families or parameters wherever the theme's palette
   differs today.
3. Adding a family or remapping a material SHALL be a data change.

### Requirement 4: Structured procedural textures

**User Story:** As a user, I want textures with real shapes, so that walls
have blocks and joints and floors have slabs, not just noise.

1. Each Texture_Family SHALL draw a 256×256 tileable diffuse with its own
   structure (blocks and mortar, slabs, planks and grain, strata, ripples…)
   and surface detail, in the material's base colour and the family's palette.
2. Two families SHALL never produce the same image for the same name and
   colour.
3. Every texture SHALL tile seamlessly (step 3's wrap rule).
4. Every texture SHALL be a pure function of its inputs: byte-identical across
   processes, with no salted `hash()` (fixing the known issue in
   `generators/textures/procedural._seed_from`).

### Requirement 5: Look conformance

**User Story:** As the project owner, I want generated textures to measure
like classic ones, so that "looks like EQ" is checked, not hoped for.

1. Each generated texture's Look_Stats SHALL lie within the theme's
   Texture_Profile p10–p90 band for every statistic, except where the
   material's base colour itself lies outside it (a lava or ice texture keeps
   its colour); exceptions SHALL be listed per family in the recipe data.
2. The sidecar's texture list SHALL carry each texture's Texture_Family and
   Look_Stats.

### Requirement 6: Texel density

**User Story:** As a user, I want textures at the classic scale, so that a
wall reads as stone blocks a player's height, not a smear across the room.

1. Box-backend UVs SHALL use the theme's measured Texel_Density per Surface
   (Open question 1 decides the target), keeping step 3's orientation rules.
2. Wilderness ground UVs SHALL use the outdoor profile's Texel_Density.
3. Only UVs SHALL change: X3's UV-free geometry goldens SHALL still pass.

### Requirement 7: Texture mode

1. The default Texture_Mode SHALL be `procedural` (the recipes); `placeholder`
   and `ai` SHALL stay selectable with `EQ_S3D_TEXTURE_PROVIDER`.
2. Tree bark and leaf textures SHALL use the recipe path too (`planks`-like
   bark grain, leaf cards keep their alpha), or stay as they are if Open
   question 4 says so.

### Requirement 8: Quick

1. Drawing every texture of a build SHALL add at most 2 s over step 3's
   placeholders on the reference machine.

### Requirement 9: Room-graph and wilderness behaviour otherwise unchanged

1. Layout, geometry, collision, regions, lights, trees, names and the
   sidecar's existing keys SHALL be unchanged for the same inputs, apart from
   UVs and texture bytes.
2. Every existing gate SHALL pass for every build that passed before.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge
   it, a step in `docs/ACCEPTANCE.md` "Step 4 — Interesting textures".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass: dungeons, cities and the Karanas read as
   Classic–PoP EverQuest at a glance, surfaces read as their material, and
   textures tile without obvious seams or repetition artefacts. The in-client
   check is M6.
