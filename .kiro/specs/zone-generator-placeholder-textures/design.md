# Design — zone-generator-placeholder-textures (roadmap step 3)

Written at master `d77cee3`. Verify against the code before working a task.

## Overview

Three parts, in build order:

1. **Names.** Material registration in the room-graph path
   (`generators/layout.py`, `generators/semantics.py`) builds each name from
   its Texture_Set and Surface instead of bare `floor`/`wall`/`ceiling` and
   `floor_<theme>`. Only the strings change: which polygons use which material
   index is untouched (Req 1.5). The same edit swaps the `<fixed-function>`
   shader for `Opaque_MaxCB1.fx` (Req 2). Wilderness names already fit.
2. **Pictures.** A new `PlaceholderProvider` (`generators/textures/
   placeholder.py`) draws a 256×256 texture from the material's base colour, a
   Surface_Class pattern and the Material_Name in a built-in bitmap font. It is
   the default Texture_Mode. The builder passes each material's Surface_Class
   through `TextureSpec`, and writes the Texture_Manifest into the sidecar.
3. **Preview.** `EqgZone.write_glb` splits the terrain into one primitive per
   material, with the TER's UVs and that material's diffuse embedded as a PNG.
   The web viewer already renders glTF materials; it needs only to stop
   overriding them and keep the overlays working.

## Research findings

Measured with `scripts`-style probes over `F:\everquest_rof2` at `d77cee3`.

1. **Classic `.s3d` zones** (befallen, blackburrow, crushbone, qeynos2,
   gukbottom, qeytoqrg, mistmoore): 19–148 textures each, all 256×256 `.bmp`.
   Names are short and grouped by set and surface: befallen `rnaflr01`,
   `rnaxwl01`, `rnaceil1`; mistmoore `tombfloor`, `tombwall`, `brickceiling`;
   gukbottom `gukf1`, `gukc1`, `gukdirt1`. So naming by set and surface is how
   the stock zones are organised, which supports Req 1.
2. **EQG zones.** Dranik catacombs and sewers: 23–27 materials named by role
   (`interior_floor`, `ext_wall_stucco_adobe_style`) with textures
   `Di_<set>_<what>01_c.dds`, all 256×256. A texture repeats about every 15 u
   (median 15.4 u, p25–p75 13–19 u). `tutoriala` repeats every ~100 u;
   `anguish` mixes 10–200 u.
3. **Our builds.** 256×256 DDS. Box zones repeat every 100 u on every
   material; wilderness ground about every 128 u (`wild_rock` ~900 u, `wild_lava`
   ~180 u). A plain dungeon or city has 3 materials (`floor`, `wall`,
   `ceiling`); a themed dungeon adds `floor_<theme>` and `wall_<theme>` for its
   rooms (`semantics._apply_materials`), and the race (`gnoll`) is in no name.
   Wilderness has 10 `wild_*` ground materials plus `liquid_water`.
4. **Classic texel density is unmeasured.** `core/wld.py` keeps texture names
   and positions but not UVs, so the classic repeat length isn't known. Step 3
   doesn't change UVs, so it doesn't need it; step 4 should measure it before
   choosing a texel density (a 15 u repeat would make stamped text unreadable).
5. **At our scale the name is readable.** At 100 u per repeat a 256 px texture
   is 2.56 px/u. A 5×7 bitmap font drawn at 2× gives glyphs 10×14 px with a
   1 px outline, about 4×6 u in the world: readable from a few metres away,
   like a sign.

## Names (`generators/layout.py`, `generators/semantics.py`)

```
texture_set(zone_type, race, key) -> str
    dungeon: "_".join(w for w in (race, key or "dungeon") if w and w != "default")
    city:    "city"
material_name(set, surface) -> f"{set}_{surface}"
```

- `layout.py` registers the shared materials as `material_name(set_shared,
  s)` for `s` in floor, wall, ceiling, where `set_shared` is
  `texture_set(zone_type, race, None)`. Rooms and corridors point at those
  names instead of `floor`/`wall`/`ceiling`.
- `semantics._material_variant(base, theme, tint)` becomes
  `material_name(texture_set("dungeon", race, tint or theme), base)`.
- The race is known before materials are registered (`spec.dungeon_race`);
  verify the order in `label_rooms` / `LayoutGenerator.generate`.
- Wilderness (`generators/wilderness/build.py`) already registers
  `wild_<layer>` and `liquid_water`; nothing changes there.
- `Opaque_MaxCB1.fx` replaces `<fixed-function>` where `layout.py` takes the
  shader from the style profile, and in `semantics._apply_materials`, which
  copies it.

The format gate (`analyzer/rof2check.py`) drops `<fixed-function>` from
`KNOWN_SHADERS` in the same task.

**Rename-only check (Req 1.5).** Before the change, record for a fixed set of
seeds per zone type a hash of the TER's vertices and of each polygon's
`(v1, v2, v3, flags, material)`. After it, the same hashes must hold. The hash
excludes material names, shaders and texture names.

## Placeholder look (`generators/textures/placeholder.py`, `font.py`)

A pure function `placeholder_rgb(name, base_color, surface_class) -> (256,
256, 3) uint8`, wrapped as `PlaceholderProvider.generate(spec) -> DDS`.

- **Background:** the base colour, flat.
- **Pattern** (lines in the base colour darkened 30 %, 2 px wide, periods that
  divide 256 so it tiles):
  - `floor`: a square tile grid, 64 px cells.
  - `wall`: running-bond brick courses, 32 px tall, 64 px long, offset by half
    a brick each course.
  - `ceiling`: diagonal hatch at 45°, 32 px apart.
  - `ground`: a dot lattice, 4 px dots on a 32 px grid, alternate rows offset.
  - `liquid`: horizontal sine waves, 32 px apart.
- **Label:** the Material_Name in a 5×7 uppercase-and-digit bitmap font
  (`font.py`, glyphs as bit rows in code: A–Z, 0–9, `_`), scale 2, 2 px letter
  spacing, drawn twice (centred at y = 64 and y = 192) inside a plate
  of the base colour lightened or darkened to give a 4.5:1 contrast with the
  text colour (white or near-black, whichever contrasts more with the plate).
  A line holds 20 characters at scale 2 (12 px per character in 240 px); a
  longer name wraps after an `_`, at most three lines (names are ≤ 40
  characters), and the plate grows to fit. Plates stay 8 px clear of
  every edge, so tiling never cuts a label.
- **Distinctness (Req 3.6):** names are unique in a build, and the label
  differs, so bytes differ.

No randomness and no `hash()`, so a Placeholder is identical across processes
(Req 3.5). The DDS is the provider's usual uncompressed format
(`generators/textures/dds.py`).

## Provider and manifest

- `TextureSpec` gains `surface_class: str = ""`.
- `factory.get_provider()` honours `EQ_S3D_TEXTURE_PROVIDER` =
  `placeholder` | `procedural` | `ai`. With no override the default is
  `placeholder` (Open question 2). `ai` keeps its procedural fallback.
- `generate_texture(...)` gains a `surface_class` argument; the builder works
  it out from the material: room-graph materials end in `_floor`, `_wall` or
  `_ceiling`; `wild_*` is `ground`; `liquid_*` is `liquid`.
- Tree bark and leaf textures don't go through this path; they keep their own
  generators (`generators/vegetation/textures.py`).
- The sidecar gains `textures`: the Texture_Manifest (Req 5). The builder
  knows each material's polygon count from the TER and the tree models.

## Preview (`core/eqg.py`, `web/src/scene.ts`)

`write_glb` gains `textures: Dict[int, bytes]` (material index → DDS bytes).
When given:

- The terrain becomes one `trimesh.Trimesh` per material in use, each with its
  own vertices (copied from the TER, so a vertex shared by two materials
  appears in both), faces, normals and `TextureVisuals(uv=..., image=...)`.
  The image is the DDS decoded to RGB (uncompressed, so exact).
- The primitives sit under one `terrain` node, so the viewer's terrain framing
  (step 2 task 9) still works.
- The glTF V axis is flipped (`v' = 1 − v`) if the probe in task 4 shows EQ's
  V runs the other way. The acceptance pass checks text reads the right way up.
- A material whose image fails to decode falls back to its base colour as a
  vertex colour, and the builder records `texture_preview_fallback:<name>`.

Without `textures` the GLB is written exactly as now (byte-identical), so a
caller that doesn't pass them is unaffected.

The viewer loads glTF materials as they come. `scene.setWireframe` already
walks every mesh's material; check it handles a mesh with several materials
(an array). The terrain-node framing and the Trees toggle are unaffected.

## Correctness properties

| P | Statement | Reqs |
|---|-----------|------|
| X1 | Every Material_Name matches `^[a-z0-9]+(_[a-z0-9]+)*$`, is ≤ 40 chars, is unique, and names its `.dds` | 1.1, 1.2 |
| X2 | For each zone type, the set and surface words follow Req 1.3–1.4 (race and theme or tint for themed dungeon rooms, `<race>_dungeon` for shared, `city`, `wild`, `liquid`) | 1.3, 1.4 |
| X3 | Rename-only: TER vertex and polygon hashes equal the pre-change goldens for every pinned seed | 1.5, 7.1 |
| X4 | No material in any build uses `<fixed-function>`; the gate rejects it | 2 |
| X5 | Placeholder: legible label (glyph height, contrast, one whole copy inside), tiles across the wrap, pure (same bytes in a fresh process), distinct per name | 3.2, 3.4–3.6 |
| X6 | Manifest: one entry per material, sorted, polygon counts sum to the meshes' | 5 |
| X7 | GLB: each material's embedded image equals its DDS within 2/255; UVs equal the TER's; positions and triangles equal the TER | 6.1, 6.2 |
| X8 | Timing: placeholders + embedding add ≤ 2 s to a dense wilderness build | 8 |

## Risks

- **UV orientation.** If EQ's V axis is flipped relative to glTF, every label
  reads upside down or mirrored in the preview. Task 4 probes it; the
  acceptance pass confirms it.
- **GLB size.** About 15 embedded 256×256 PNGs add ~1–2 MB per preview. Fine
  locally; noted.
- **Box zones repeat at exactly 100 u.** A label repeats every 100 u along a
  wall; that's the point for a placeholder, but it will look busy. Step 4
  decides the real density.
- **Wilderness UVs vary per layer** (`wild_rock` ~900 u per repeat): its label
  will be huge. Acceptable for a placeholder; noted for step 4.

## Open questions

1. **What a Placeholder shows.** Default: base colour, Surface_Class pattern
   and the Material_Name as text. Alternatives: pattern and colour only, no
   text (looks less like a debug view, but you can't read the name); or text
   only on a flat colour.
2. **Default Texture_Mode.** Default: `placeholder` for every build while step
   3 stands, with `procedural` still selectable. Alternative: keep
   `procedural` as the default and make placeholders opt-in.
3. **Textured preview in step 3.** Default: yes (Req 6), since otherwise the
   placeholders can only be seen in the client (M6). Alternative: defer it to
   step 4 and judge step 3 from the files and the manifest.
4. **Race in the set name.** Default: yes, race first (`gnoll_temple_wall`),
   matching the roadmap's `gnoll-cave-wall` example. Alternative: theme only
   (`temple_wall`), so two races sharing a theme share textures.

## Decisions

1. Names change; geometry and material assignment don't (Req 1.5, X3).
2. UV scale and texel density are untouched; step 4 measures classic density
   first (finding 4).
3. Tree textures keep their own generators and names; the preview keeps trees
   in base colours.
4. The `<fixed-function>` follow-up from step 2 is fixed here, since step 3
   touches the same registration code.
