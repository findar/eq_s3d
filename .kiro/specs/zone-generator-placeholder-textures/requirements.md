# Requirements Document

> **STATUS: roadmap step 3, ready.** Written 2026-11-01. The user answered the
> design's open questions the same day (`archive.md` "Decisions"). Task index:
> `tasks.md` (card format, 10 tasks).

## Introduction

Roadmap step 3: **placeholder textures, enough to identify type.** Today every
material gets a noise texture tinted with its base colour, and a dungeon or
city has three materials named just `floor`, `wall` and `ceiling`. Neither the
names nor the pictures say what a surface is meant to be, so a person can't
tell which texture belongs where, and step 4 (the real texture pass) has no
list of what to make.

Step 3 makes every surface say what it is. Each material gets a name built
from its texture set and its surface (`gnoll_temple_wall`, `city_floor`,
`wild_plains`), and a placeholder texture that shows that name over a pattern
for its kind of surface. The browser preview shows the textures, so the user
can see them without loading the client, and the sidecar lists every texture
the zone needs.

Measured on the stock client (`F:\everquest_rof2`, design "Research
findings"), classic zones use 19–148 textures of 256×256, named by set and
surface (`rnaflr01`, `rnaxwl01`, `rnaceil1`; `tombfloor`, `tombwall`). Step 3
keeps our 256×256 size and our texel scale (one repeat per 100 u in box zones,
about 128 u in wilderness), which leaves a stamped name readable.

This spec sits under the umbrella `zone-generator`
(`.kiro/specs/zone-generator/`). "Req X.Y" below means a requirement of THIS
spec unless it says "umbrella".

**What it takes from the umbrella.** Umbrella Req 17 (textured preview) is
delivered here for diffuse textures on the terrain: criteria 17.1, 17.2
(diffuse only), 17.4, 17.5 and 17.6. Normal maps (umbrella Req 16, 17.2's
normal half, 17.3) stay with step 4.

**Out of step 3:** good-looking textures (step 4), normal maps, a change to
UV scale or texel density, textured trees in the preview (tree models keep
their bark and leaf textures in the `.eqg` and base colours in the preview),
new materials or a different split of surfaces into materials, and an
in-client check (M6).

## Glossary

- **Surface**: what a material covers. For room-graph zones: `floor`, `wall`
  or `ceiling`. For wilderness: its ground layer (`plains`, `drygrass`, `dirt`,
  `rock`, `cliff`, `mud`, `rim`, `lava`, `zoneline`, `water`) or `water` for
  the liquid surface.
- **Surface_Class**: the pattern family a Surface draws with: `floor`, `wall`,
  `ceiling`, `ground` (every wilderness ground layer) or `liquid`.
- **Texture_Set**: the lowercase words naming the family a material belongs
  to: for a dungeon, the race (when set and not `default`) then the archetype or elemental tint
  (`gnoll_temple`, `lava`) for themed rooms, or the race then `dungeon` for
  shared surfaces (`gnoll_dungeon`); `city` for a city; `wild` for wilderness
  ground; `liquid` for liquid surfaces.
- **Material_Name**: `<Texture_Set>_<Surface>`, lowercase words joined by `_`
  (`gnoll_temple_wall`, `city_ceiling`, `wild_plains`, `liquid_water`). The
  material's texture file is `<Material_Name>.dds`.
- **Placeholder**: the 256×256 diffuse texture step 3 draws for a material:
  its base colour, a Surface_Class pattern and its Material_Name as text.
- **Texture_Manifest**: the sidecar's `textures` list: one entry per material
  with its Material_Name, texture file, Texture_Set, Surface, Surface_Class,
  polygon count and whether it is a Placeholder.
- **Texture_Mode**: which provider draws the zone's textures: `placeholder`,
  `procedural` or `ai`.

## Requirements

### Requirement 1: Every material is named by set and surface

**User Story:** As a zone author, I want every material named for what it is,
so that I know which texture to make or swap for each surface.

1. THE Zone_Builder SHALL give every material of a dungeon, city or wilderness
   build a Material_Name of the form `<Texture_Set>_<Surface>`, made of
   lowercase ASCII letters and digits in `_`-joined words, at most 40
   characters, and unique within the build. (The longest today is 33:
   `lizardman_corrupted_sanctum_floor`.)
2. THE material's diffuse texture SHALL be packed as `<Material_Name>.dds` and
   referenced by its `e_TextureDiffuse0`.
3. A dungeon's themed room materials SHALL use the race (when set) and the
   archetype or elemental tint as Texture_Set; its shared materials (corridors,
   unthemed rooms, every ceiling) SHALL use the race (when set) and `dungeon`.
4. A city's materials SHALL use Texture_Set `city`. Wilderness ground
   materials keep their `wild_<layer>` names and the liquid surface keeps
   `liquid_water`.
5. THE renaming SHALL change no geometry and no material assignment: for the
   same inputs, every TER vertex and every polygon's vertices, flags and
   material index are what they were before step 3.
6. Tree models (`veg_<species>.mod`) and their textures SHALL keep their names.

### Requirement 2: Real shaders

**User Story:** As the project owner, I want every material to use a shader
the client knows, so that no surface depends on a placeholder shader name.

1. THE dungeon and city materials SHALL use `Opaque_MaxCB1.fx` where they now
   carry the style profiles' `<fixed-function>` placeholder.
2. THE Tier-1 format gate SHALL no longer accept `<fixed-function>` as a known
   shader.

### Requirement 3: Placeholder textures identify their surface

**User Story:** As a user, I want each texture to show what it is, so that I
can tell surfaces apart and read their names in the 3D view.

1. In Texture_Mode `placeholder`, THE Texture_Generator SHALL draw each
   material's diffuse as a 256×256 Placeholder: the material's base colour, a
   pattern for its Surface_Class, and its Material_Name as text.
2. THE text SHALL be legible: at least 12 px tall per glyph, drawn with a
   contrast ratio of at least 4.5 against the pixels around it, and at least
   one full copy of the name SHALL lie inside the texture without crossing an
   edge.
3. THE five Surface_Class patterns SHALL be distinct from one another (design
   "Placeholder look").
4. THE Placeholder SHALL tile seamlessly: across the wrap, the largest
   per-channel difference between the last and first rows (and columns) is no
   larger than the largest difference between two adjacent rows (columns)
   inside the texture.
5. THE Placeholder SHALL be a pure function of (Material_Name, base colour,
   Surface_Class): byte-identical across runs and processes, with no random
   or hash-salted input.
6. Two materials in one build SHALL never get identical Placeholder bytes.

### Requirement 4: Texture mode

**User Story:** As a user, I want placeholders by default during step 3, and
the old procedural look still available.

1. THE default Texture_Mode SHALL be `placeholder`.
2. `EQ_S3D_TEXTURE_PROVIDER` SHALL select `placeholder`, `procedural` or `ai`;
   `ai` falls back to `procedural` on any failure, as today.
3. THE Texture_Manifest SHALL record the Texture_Mode that drew each texture.

### Requirement 5: Texture manifest

**User Story:** As a zone author, I want a list of every texture the zone
uses, so that step 4 (or I) can replace them one by one.

1. THE sidecar SHALL carry a Texture_Manifest with one entry per material in
   the build, tree materials included, each with its Material_Name, texture
   file, Texture_Set, Surface, Surface_Class, polygon count and Texture_Mode.
2. Entries SHALL be sorted by Material_Name, and their polygon counts SHALL
   sum to the polygon count of the TER and tree models they describe.

### Requirement 6: Textured preview

**User Story:** As a user, I want the browser preview to show the textures, so
that I can judge them without loading the client (umbrella Req 17).

1. THE GLB `terrain` node SHALL draw each material with the same diffuse
   texture packed in the `.eqg` (same size; a PNG is allowed, each channel
   within 2/255 of the DDS texel) and SHALL keep each vertex's UVs from the TER
   (umbrella 17.1).
2. THE GLB `terrain` node's vertex positions and triangles SHALL equal the TER
   (umbrella 17.6); vertices may be duplicated where materials meet.
3. IF a material's texture can't be embedded, THEN that material SHALL fall
   back to its base colour, the build SHALL record a warning naming the
   material, and the GLB and `.eqg` SHALL still be written (umbrella 17.4).
4. THE Web_App SHALL render each preview material with its texture, and a
   material without one with its base colour (umbrella 17.2, 17.5).
5. THE `vegetation` node SHALL stay as it is (base colours).
6. THE wireframe, Trees and other overlay toggles SHALL keep working.

### Requirement 7: Room-graph and wilderness behaviour otherwise unchanged

**User Story:** As the project owner, I want step 3 to change only names,
shaders and pictures.

1. Layout, geometry, collision, regions, lights, trees and the sidecar's
   existing keys SHALL be unchanged for the same inputs, apart from material
   and texture names.
2. Every existing gate (traversability, bowl, trunk walkability, Tier-1
   format) SHALL pass for every build that passed before.

### Requirement 8: Quick

**User Story:** As a user, I want placeholders not to slow generation.

1. Drawing every Placeholder of a build and embedding the textures in the GLB
   SHALL add at most 2 s to a build on the reference machine.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge it,
   a step in `docs/ACCEPTANCE.md` "Step 3 — Placeholder textures".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass: in the 3D view each surface shows its name
   and pattern, the names match what the surfaces are, and the textures sit
   the right way up and tile without seams. The in-client check is M6.
