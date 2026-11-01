# Design — zone-generator-wilderness-trees (roadmap step 2)

Written 2026-10-31 at master `f28ff85`. Requirements: `requirements.md`.

## Overview

Trees are a layer on top of the finished wilderness. Terrain, bowl gate,
outline and maps are built exactly as in step 1. Trees then add:

- one generated `.mod` per Species;
- one ZON object per tree;
- a `vegetation` node in the GLB;
- a `vegetation` block in the sidecar;
- one extra check in the wilderness gate.

The TER is never touched (Req 7).

```
plan_to_spec ─► wilderness_spec (spec.wilderness gains "trees")
TerrainBackend ─► build_wilderness_ter            (unchanged)
                     │
                     ▼
               vegetation_for(spec, ter) ─► Vegetation{models, instances, textures, report}
                     │                         ▲
   ZoneBuilder ──────┤ packs .mod + textures,  │ kit (styles/vegetation.json)
                     │ ZON objects, GLB node,  │ models.py   placement.py
                     │ sidecar block           │
   bowl_report ──────┘ + trunk walkability check (Req 6)
```

`vegetation_for` is pure in `(spec, ter)` and cached like `landscape_for`, so
the builder and the gate get the same trees without passing them around.

## Research findings

All measured on `F:\everquest_rof2` on 2026-10-31. The scratch scripts read
`objects.wld` 0x15 placements and `<zone>_obj.wld` 0x36 meshes from the classic
`.s3d` files, plus ZON objects from EQGZ-format `.eqg` files. Their method is
in the task 4 card, so the numbers can be re-derived.

1. **Karana tree counts and density.** Density is measured against each zone's
   bounding-box area, which over-counts the playable area:

   | Zone | Trees | Species | Trees per 10⁶ u² | NN p10 / p50 / p90 (u) | Grove_Ratio |
   |------|------:|--------:|-----------------:|-----------------------:|------------:|
   | northkarana | 1,868 | 5 | 27.8 | 23 / 60 / 122 | 0.67 |
   | southkarana | 3,700 | 3 | 31.6 | 24 / 58 / 118 | 0.70 |
   | eastkarana | 1,339 | 6 | 12.1 | 26 / 59 / 120 | 0.44 |
   | qeytoqrg | 366 | 4 | 11.8 | 37 / 89 / 172 | 0.65 |
   | ecommons | 1,491 | 3 | 37.6 | 17 / 39 / 76 | 0.51 |

   The Grove_Ratio is below 1 everywhere, so the trees are clustered, not
   scattered evenly. NN p10 is about 24 u: the closest trees stand about four
   trunk-widths apart. Other outdoor zones agree. gfaydark (a dense forest) has
   77 trees per 10⁶ u², and rathemtn 25.
2. **Karana tree models are tiny.** TREE5, TREETRY, TREE71, TREE10 and BPINE1
   each have 31–40 polygons. About 15 are solid trunk and 16 are passable
   (WLD flag 0x10) canopy: double-sided leaf cards. They are 35–90 u wide and
   46–130 u tall; the big pine RPINE1 is 304 u. Every model's lowest vertex is
   2–6 u below its origin (RPINE1 40 u), so the trees are sunk into the
   ground.
3. **Scale and species vary.** Each zone places 3–6 species with per-instance
   scale between 0.10 and 2.25 (northkarana: 1.0 except one pine at
   0.75–1.25).
4. **EQG trees use the same split.** The `OBP_` trees in broodlands and
   draniksscar have every triangle passable. The `OBJ_` burnt trees in
   bloodfields are fully solid. Leaves use `Chroma_*` or `Alpha_*` shaders and
   trunks use `Opaque_*`. The classic trunk-solid, canopy-passable split is the
   Karana look, so it's the default (Open question 1).
5. **ZON rotations are radians, and the first rotation field is yaw.** On stock
   trees, the field `core/zon.py` calls `rx` spans ±π, and the other two stay
   within ±0.2. `core/zon.py` currently treats all three as heading units
   (0–512) and converts to degrees. `ZonFile.place(rz=…)` therefore writes yaw
   into a tilt field, in the wrong unit. No code places objects yet, so nothing
   is wrong on master today, but step 2 must fix this first (task 1).
6. **ZON object positions are in the TER frame, Z up, not swapped.** On
   broodlands, the median tree Z is 2.5 u below the nearest TER vertex. With X
   and Y swapped it is 66 u off. That agrees with finding 2's sunk bases.
7. **About half the stock EQG zones use the text-based `EQTZ` zone format** (53
   of 88). Our reader only handles `EQGZ`, which is the format we write. Not
   needed for step 2.

## Vegetation kit (`styles/vegetation.json`, `generators/vegetation/kit.py`)

```json
"plains_grassland": {
  "density": {"sparse": 10, "normal": 22, "dense": 45},
  "groves": {"lone_share": 0.25, "radius": [50, 140], "trees_per_grove": [4, 14]},
  "species": {
    "broadleaf": {"form": "broadleaf", "weight": 0.5, "height": [70, 110], "canopy": [55, 80],
                  "trunk_radius": 3.5, "scale": [0.6, 1.6],
                  "bark": [92, 74, 52], "leaf": [86, 118, 54]},
    "conifer":   {"form": "conifer",   "weight": 0.3, "height": [90, 130], "canopy": [40, 60],
                  "trunk_radius": 3.0, "scale": [0.6, 1.75], "bark": [84, 66, 50], "leaf": [52, 88, 58]},
    "sapling":   {"form": "broadleaf", "weight": 0.2, "height": [40, 55],  "canopy": [28, 38],
                  "trunk_radius": 1.8, "scale": [0.5, 1.4],  "bark": [96, 80, 58], "leaf": [104, 132, 62]}
  }
}
```

The densities are per 10⁶ u² of Eligible_Ground, which is denser than the
Karanas' bounding-box figures. The figures above are a starting point, tuned in
task 11. `kit.py` validates the entry (Req 1.1). `biomes.json` keeps carrying
only the id.

## Tree models (`generators/vegetation/models.py`)

`tree_model(species, seed) -> TerFile` (magic `EQGM`), in model space with
the origin at ground level and Z up:

- **Trunk:** a 6-sided prism tapering from `trunk_radius` to
  0.6 × `trunk_radius`. It runs from z = −12 (buried, Req 2.4 and 5.3) up to
  45 % of the height, has a 4-triangle top cap, and has no bottom cap: 16
  triangles, flag 0, opaque shader, bark texture.
- **Broadleaf canopy:** 4 vertical cards crossed at 45° through the crown
  centre, each double-sided by duplicating it with reversed winding: 16
  triangles, flag `0x01`, chroma shader, leaf texture with a rounded,
  noise-edged silhouette in alpha. Crown radius is `canopy`/2, centred at
  about 70 % of the height.
- **Conifer canopy:** 3 stacked tiers. Each tier is 2 crossed double-sided
  cards with a triangular silhouette in alpha, narrowing upward: 24 triangles.
- Height, crown size and a slight lean (≤ 3°) are drawn from the seed within
  the species ranges, so two seeds give two different-looking trees.
  `models.py` emits one model per Species per zone; Tree_Instances add
  variety through scale and yaw.

Totals: broadleaf and sapling 32 triangles, conifer 40, inside Req 2.2's
24–96 and close to the Karana models' 31–40.

**Textures** (`generators/vegetation/textures.py`):

- Bark is the normal procedural texture path (`generate_texture` with the
  bark description and colour).
- Leaves need an alpha silhouette, which the provider path doesn't make, so
  `leaf_texture(form, colour, seed)` builds the RGB with the procedural
  provider and the alpha mask procedurally, then encodes with
  `dds.rgba_to_dds(rgb, alpha)`.
- With an AI key set, the RGB may come from the provider; the alpha mask is
  always procedural.

Texture names are `veg_<species>_bark.dds` and `veg_<species>_leaf.dds`.

## Placement (`generators/vegetation/placement.py`)

`place_trees(land, ter, kit, level, seed) -> List[TreeInstance]`, pure.

1. **Eligible_Ground on TER quads.** A quad is eligible when:
   - both of its triangles are standable and at most 30° steep;
   - its fine cell's Node_Type is `plains`, and it isn't a Rim seal cell;
   - it lies outside Kept_Clear: within 120 u of Spawn, the zoneline gap cells
     plus 2 fine cells inward, or within 1 fine cell of `water`/`river`.

   Working on quads, not fine cells, means "eligible" is exactly the ground the
   walk surface stands on.
2. **Target count** is the kit density for the level × eligible area.
3. **Grove centres:**
   - Choose `(1 − lone_share) × target / mean(trees_per_grove)` centres by
     Poisson-disc sampling over eligible quads, spaced 2 × the max grove
     radius.
   - Each grove gets a radius, a size and a dominant Species: the dominant
     Species takes 70 % of its trees, and the rest follow the kit weights.
4. **Dart throwing** (a Thomas cluster process):
   - A candidate is Gaussian around a grove centre (σ = radius / 2), or
     uniform over eligible ground for lone trees.
   - It's accepted only when its Trunk_Disc grown by Tree_Clearance lies
     wholly on eligible quads and clears every accepted disc by
     Tree_Clearance.
   - A spatial hash with 32 u buckets makes each test O(1).
   - Stop at the target, or after 30 × target attempts. Falling short of 75 %
     of the target records `vegetation_capped` (Req 5.5).
5. **Per instance:**
   - yaw uniform in [−π, π);
   - scale uniform in the Species range;
   - Z = the TER surface at XY, from the triangle under the point (closed-form
     on the regular grid).

   With slope ≤ 30° and trunk radius × scale ≤ 6.1 u, the surface varies by at
   most 3.5 u across the disc, and the trunk is buried 12 × scale ≥ 6 u, so
   Req 5.3 holds with margin.

**Seeding:** `seed` is derived from the zone seed with a fixed salt
(`_stable_seed(seed, "vegetation")`). That keeps step 1's terrain random stream
untouched (Req 7.1). The level changes only the target count and the
attempt budget, never the terrain.

## Walkability (Req 6)

**Why it holds by construction (Req 6.3).** Every Trunk_Disc grown by
Tree_Clearance (8 u) lies inside eligible ground. Eligible ground is walkable,
and grown discs are pairwise disjoint. The walkable region is open and
connected (step 1's gate), and the trees cut out a set of disjoint closed
discs strictly inside it. Removing disjoint closed discs from the interior of
an open connected planar region leaves it connected. So the trees can't
disconnect anything, and a gap of at least 8 − 2 × 1.5 u stays free beside
every trunk for a player 3 u wide.

**The gate check (Req 6.1) verifies it anyway**, because the argument relies
on eligibility being computed right:

- `bowl_report` gains `trees_block(spec, ter)`.
- It rasterises the reachable standable TER faces at 2 u, subtracts Trunk_Discs
  grown by 1.5 u, and labels the result with `scipy.ndimage.label`.
- It then requires Spawn's component to touch every playable fine cell and
  every zoneline gap.
- On 2400 u that's 1.44 M pixels, well under a second.
- A failure adds a problem naming a cut-off cell, so the bowl "room" fails and
  the Pipeline retries (Req 6.2).

## Build integration

- **`generators/wilderness/build.py`:**
  - `wilderness_spec` adds `"trees": level` and `"trees_source"` to
    `spec.wilderness`.
  - `vegetation_for(spec, ter)` returns models, instances, textures and the
    sidecar report.
  - `bowl_report` calls the trunk check.
- **`generators/builder.py`**, for wilderness specs with instances:
  - packs `veg_<species>.mod` with `eqg.add_model`, and packs their textures;
  - `_build_zon` appends each model name after `TER_<NAME>.TER` and adds one
    `ZonObject` per instance (`name = f"veg_{i:04d}"`, yaw in the yaw field,
    in radians, per task 1);
  - merges the `vegetation` block into the sidecar `extra`.

  Room-graph specs take none of these paths (Req 10).
- **`core/zon.py` (task 1):**
  - Rotation is read and written in radians. `ZonObject` gets
    `yaw`/`pitch`/`roll` named for what they do, with `yaw` mapped to the
    first field.
  - `ZonRegion.rotation` is checked against stock regions the same way, and
    fixed only if it's wrong too.
  - A regression test reads stock broodlands and asserts the yaw spread is
    about ±π.
- **`core/eqg.py` `write_glb`:**
  - Takes an optional list of extra meshes, each a name plus a trimesh with
    per-vertex colour.
  - With extras it exports a `trimesh.Scene` with the nodes `terrain` and
    `vegetation`.
  - Without extras the output is byte-identical to today.
- **`analyzer/rof2check.py`:** adds the object/model/texture/shader checks of
  Req 8.3.

## Density control (Req 3)

`trees` travels like `edges`: outside the Zone_Plan, into `spec.wilderness`.

- **Prompt:** `resolve_wilderness_intent` gains the density words and records
  `trees_source: "prompt"`.
- **CLI:** `--trees`, rejected with exit 2 unless `--zone-type wilderness`.
- **Server:** `_require_trees` mirrors `_require_edges` (400 before any write).
- **Web:** a Trees `<select>` beside the Edges selectors, plus a "Trees"
  checkbox in the viewer overlays that sets the `vegetation` node's
  `visible`.

## Correctness properties

All Hypothesis properties use the default and `thorough` profiles. Wilderness
builds are slow, so the build-level properties take few examples (`slow`
marker), as in step 1.

| P | Statement | Reqs |
|---|-----------|------|
| T1 | Every Tree_Model has 24–96 triangles, ≥ 1 trunk (flag clear) and ≥ 1 canopy (flag set), trunk min z ≤ −2, and round-trips through `core.ter` | 2.2–2.4, 2.6 |
| T2 | Every Trunk_Disc grown by Tree_Clearance lies on eligible quads; grown discs are pairwise disjoint | 4.1–4.3 |
| T3 | Grove_Ratio ∈ [0.45, 0.85], density within ±25 % (or capped and recorded), species share within ±15 points, on zones with ≥ 40 trees | 5.2, 5.5, 5.6 |
| T4 | Z equals the surface at XY; the buried trunk reaches ≥ 2 u below the surface everywhere on the disc | 5.3 |
| T5 | TER bytes identical across all four levels | 7.1 |
| T6 | The trunk walkability check passes for every seed | 6.1, 6.3 |
| T7 | ZON lists each packed model once after the TER; each object's model index resolves; instance names unique; yaw within [−π, π) | 8.1, 8.2 |
| T8 | `none` places nothing and packs no `.mod`; dungeon/city EQG bytes unchanged | 4.4, 10.1 |
| T9 | Same inputs give byte-identical `.eqg` | 11.1 |
| T10 | Stock ZON yaw is read as radians in the first field (example test on broodlands, skipped without `EQ_PATH`) | task 1 |

## Testing notes

- Placement properties run on synthesized landscapes (`synthesize_landscape`
  is about 50 ms), not full builds.
- Build properties use 3–5 seeds.
- Timing (Req 11.2) is one `slow` test with a generous ceiling, as step 1's
  Property 16 timing test is.
- No frontend test framework exists. The web selector and the toggle are
  checked by hand in the acceptance pass.

## Risks

- **The GLB becomes a scene with two nodes.** Code that assumes `gltf.scene`
  holds one mesh (camera framing, the walk-height raycast) may misbehave.
  Task 9 checks `web/src/scene.ts` for that.
- **Alpha-tested leaves in the GLB preview** are drawn as solid base colour
  (lessons-learned: no real textures in the preview). The 3D view will show
  card-shaped canopies. That's expected until the texture steps; the
  acceptance section should say so.
- **The in-client look of chroma leaves isn't verified** until M6 can load a
  zone. Shader choice follows the stock trees (finding 4).

## Open questions

1. **Tree collision.** The default is a solid trunk with a walk-through
   canopy, as in the classic Karanas. The alternative is fully walk-through
   trees, like the `OBP_` trees: simpler, and they can never block anything,
   but you could run through a trunk.
2. **Density control.** The default is prompt words plus a Trees selector
   (none / sparse / normal / dense) on the web and CLI. The alternative is one
   fixed density, with no control in step 2.
3. **Trees on the rim slopes.** The default is none: trees only on plains
   below 30°, so the mountain rim stays bare rock. The alternative is a
   sparse scattering on the lower scenic rim slopes, which the Karanas have.
4. **Trees on maps.** The default is none on the EQ `.txt` (stock maps don't
   draw trees) and none on the web SVG in step 2. The alternative is a dot
   layer on the web SVG.

## Decisions

1. Trees are generated `.mod` models packed in the zone's own `.eqg`, never
   stock models (umbrella Req 32.7).
2. Umbrella Req 32.4 is refined for wilderness vegetation only; this is
   recorded in the umbrella at the close task.
3. `trees` rides in `spec.wilderness` like `edges`. There's no Zone_Plan
   schema change.
4. Placement salts its own random stream, so the terrain never moves (Req 7).
5. Walkability is guaranteed by construction (grown discs on eligible ground)
   and verified by a raster check in the existing gate.
