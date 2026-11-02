# Design — zone-generator-interesting-textures (roadmap step 4)

Written at master `ca3a61a`. Verify against the code before working a task.

## Overview

Measure, then match:

1. **Read classic UVs** (`core/wld.py`) and **measure** texel density per
   surface and the look of every 256×256 texture into each theme's style
   profile (`analyzer/style_builder.py`, `styles/*.json` `textures` block).
2. **Recipes** (`styles/texture_recipes.json`, `generators/textures/recipes.py`)
   map each Material_Name to a Texture_Family and its parameters.
3. **Painters** (`generators/textures/painters/`) draw each family as a
   structured, tileable, pure 256×256 diffuse, then a **conformance** pass
   checks its Look_Stats against the profile.
4. **Texel density** from the profile drives box-backend and wilderness UVs.
5. The recipes become the default Texture_Mode; placeholders and AI stay
   selectable; the sidecar texture list gains the family and Look_Stats.

## Research findings

Measured at `ca3a61a` over `F:\everquest_rof2` with scratch probes (the
reader changes in task 1 make them repeatable).

1. **Classic texel density** (0x36 texcoords; old format int16 / 256),
   per-zone medians, world units per repeat:

   | zone | wall | floor | ceiling |
   |------|------|-------|---------|
   | befallen | 14.0 | 41.8 | 14.0 |
   | unrest | 14.0 | 13.1 | 14.0 |
   | najena, qcat, gukbottom | 14.0 | 14.0 | 14.0 |
   | mistmoore | 12.2 | 12.0 | 28.0 |
   | soldunga | 14.2 | 27.9 | 29.7 |
   | kaesora | 16.1 | 32.0 | 31.9 |
   | charasis | 18.2 | 35.3 | 18.0 |
   | sebilis | 24.0 | 36.0 | 18.1 |
   | crushbone | 30.1 | 80.2 | 39.9 |
   | blackburrow | 49.0 | 49.7 | 29.8 |
   | qeynos2 (city) | 14.0 | 29.9 | 14.0 |
   | qeytoqrg (outdoor) | 43.0 | 22.5 | 62.3 |
   | nektulos (outdoor) | 72.2 | 103.0 | 110.3 |
   | qey2hh1 (outdoor) | 150.7 | 268.4 | 314.1 |

   Dungeons cluster at 14 u on walls; floors run coarser (14–40 u). Outdoor
   zones are coarser still (43–110 u). Ours: 100 u everywhere in box zones,
   ~128 u in wilderness.
2. **Classic UV direction.** Classic WLD walls run `v` up as `z` rises (no
   more than 12 % of wall edges run it down in any of the 16 zones; 0 % in
   13): their `.bmp` images are stored bottom-up. EQG
   zones run it down (step 3, task 4). We write EQG, so step 3's convention
   stands.
3. **Classic look** (1,087 256×256 textures from 15 zones) against ours
   (6 procedural materials):

   | statistic | classic p25 | p50 | p75 | ours |
   |-----------|------|------|------|------|
   | luminance mean | 0.163 | 0.228 | 0.303 | 0.409 |
   | luminance std | 0.053 | 0.076 | 0.110 | 0.090 |
   | saturation | 0.282 | 0.406 | 0.585 | 0.166 |
   | edge energy | 0.015 | 0.028 | 0.038 | 0.007 |

   Ours are too bright, too grey and far too smooth. Contrast is about right.
4. **The profiles don't measure texture today.** `styles/*.json` `uv.scale`
   is always 1.0 (a placeholder) and `materials` holds only a count and the
   `<fixed-function>` marker.
5. **Normal maps:** classic `.s3d` zones have none (no shader stage);
   GoD+ `.eqg` zones use `e_TextureNormal0`. Umbrella Req 16 plans them.

## Reader (`core/wld.py`)

`WldMesh` gains `uvs: List[Tuple[float, float]]` and
`polygon_textures: List[int]` (expanded from the polygon-texture groups,
`count, texture_index` pairs after the vertex pieces). Old format: int16 / 256;
new: int32 / 256. A mesh whose texcoord count doesn't match its vertex count
keeps `uvs = []`.

## Texture_Profile (`analyzer/style_builder.py`)

```
"textures": {
  "texel_density": {"wall": {p25, p50, p75}, "floor": …, "ceiling": …},
  "look": {"lum_mean": {p10, p50, p90}, "lum_std": …, "saturation": …,
           "edge_energy": …},
  "zones": [...], "textures_measured": N
}
```

Surfaces are classified by face normal (|nz| < 0.3 wall, nz > 0.7 floor,
nz < −0.7 ceiling). Look_Stats run over every 256×256 `.bmp`/`.dds` in the
theme's zones except `palette.bmp`. The `uv` block is replaced.

## Recipes (`styles/texture_recipes.json`, `generators/textures/recipes.py`)

```
"families": {"dressed_stone": {"block": [64, 32], "joint": 3, "bevel": 2,
                                "jitter": 0.12, "grain": 0.35}, ...},
"materials": [
  {"set": "*_temple", "surface": "wall",  "family": "dressed_stone", ...},
  {"set": "*_tomb",   "surface": "wall",  "family": "dressed_stone", "block": [48, 48]},
  {"set": "*_dungeon","surface": "ceiling","family": "cave_rock"},
  {"set": "city",     "surface": "floor", "family": "cobble"},
  {"set": "wild",     "surface": "plains","family": "grass"}, ...
],
"fallback": {"wall": "dressed_stone", "floor": "flagstone",
             "ceiling": "cave_rock", "ground": "dirt", "liquid": "water"}
```

Match order: exact set, then the set's last word (theme or tint) with a `*_`
pattern, then the Surface fallback. `resolve(name) -> (family, params,
source)`.

## Painters (`generators/textures/painters/`)

Each family is `paint(params, base_color, seed) -> (256, 256, 3) uint8`,
seeded from `zlib.crc32` of the material name (never `hash()`). Shared
building blocks: tileable value noise (existing), tileable Worley/Voronoi
cells (stones, cobble, cave rock), a running-bond and an ashlar layout (brick,
dressed stone), plank strips with grain, and a palette jitter per cell. Detail
is high-frequency (edge energy target ~0.03), structure mid-frequency, colour
pulled toward the profile's luminance and saturation bands.

## Conformance

`look_stats(rgb)` (in `generators/textures/conformance.py`) and a property:
for every family × a sample of themes × colours, the result lies in the
theme's p10–p90 band on all four statistics, unless the recipe lists an
exception for that statistic (lava saturation and brightness, ice brightness,
sky). The builder records Look_Stats in the sidecar texture list.

## Texel density

`MeshBuilder.add_quad(uv_scale=…)` already takes a scale; the box backend
passes `1 / density[surface]` from the theme's Texture_Profile instead of the
fixed 0.01. Wilderness passes the outdoor profile's ground density. X3's
UV-free goldens must still pass.

## Correctness properties

| P | Statement | Reqs |
|---|-----------|------|
| Y1 | WLD UVs: on 5 stock zones the texcoord count equals the vertex count and the per-zone wall median matches the research table within 0.5 u | 1 |
| Y2 | Profile: re-running the analyzer gives byte-identical `textures` blocks | 2.3 |
| Y3 | Every Material_Name a build can produce resolves to a family; unmatched names are recorded | 3.1 |
| Y4 | Painters: tileable, pure across processes, distinct per family | 4 |
| Y5 | Look_Stats within the profile band except listed exceptions | 5 |
| Y6 | UVs follow the profile density; UV-free goldens unchanged | 6 |
| Y7 | Timing ≤ 2 s over placeholders on a dense wilderness build | 8 |

## Risks

- **Classic density with our big rooms.** At 14 u a 300 u wall repeats a
  texture ~21 times; repetition artefacts will show. Structure with per-cell
  variation hides most of it; a human must judge (exit criterion 3).
- **Placeholders at classic density** have tiny labels (a 14 u repeat makes a
  glyph about 0.8 u tall). Open question 1.
- **"Within the classic band" isn't "looks like EQ".** The statistics are a
  floor; the look needs the human pass.

## Open questions

1. **Texel density target.** Default: the theme's measured p50 per surface
   (dungeon walls ~14 u, floors ~30 u, ceilings ~18 u; outdoor ground ~60 u),
   with placeholder mode keeping step 3's 100 u so labels stay readable.
   Alternatives: the measured p50 in every mode; or a compromise (~30 u) that
   reads less tiled in our larger rooms.
2. **Normal maps in step 4.** Default: no. The Classic–PoP default look has
   none; umbrella Req 16 stays planned for later (an option for a GoD-style
   look). Alternative: deliver Req 16 here (a normal map per material from the
   painter's height field, `e_TextureNormal0`, and in the preview).
3. **Scope of families.** Default: all three zone types (dungeon, city,
   wilderness), 15 families. Alternative: dungeon and city first, wilderness
   ground in a later step.
4. **Tree textures.** Default: bark through the `planks` grain painter and
   leaves through a `foliage` painter with the existing alpha, so trees match
   the new ground. Alternative: leave tree textures as they are.

## Decisions

1. Measure first: the profile is the target, and every statistic in Req 5 is
   checked against it.
2. Recipes are data; painters are code; the mapping never guesses from words.
3. Geometry and names don't change; only UVs and texture bytes do.
4. The salted-`hash()` seed in the procedural path is fixed here (Req 4.4).
