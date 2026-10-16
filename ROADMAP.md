# Roadmap & Open Items

The authoritative list of what's done, what's next, and known gaps. The README
carries the narrative "what it does / how it works"; this file is the tracker.
Keep it in sync when work lands (check items off, move them, note the commit).

Last updated: commit `f9c5243` (29 commits, 144 tests passing).

---

## ▶ Pick up here (next session)

Most recent work: fixed the organic cave generation — chambers were
disconnected floating blobs and floors rendered see-through. Root causes were
an inverted `smooth_min`, tunnels not reaching the inscribed-sphere chambers,
and backwards floor winding. All fixed and regression-tested (commit `f9c5243`).

**Suggested next step:** eyeball the cave fix in the web viewer against
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) sections B/C/D (navigability,
enclosure, cave shapes) for a few seeds — the fix is verified by automated tests
and mesh analysis, but has NOT yet been confirmed by a human walking it in 3D.
Once that looks right, start **Phase 4 — Refinement** (below): the iterative
chat loop is the highest-leverage feature.

**Validate major changes** with the acceptance checklist in
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md).

---

## Done

| Area | Summary |
|------|---------|
| Analyzer (Phase 0) | Extract style metrics from a RoF2 install; profiles in `styles/` |
| Core I/O (Phase 1) | PFS read/write (EQ big-endian CRC), TER/ZON serialisers, EQG assembler |
| WLD reader | Classic–PoP `.s3d`/WLD geometry reader (0x36 meshes) |
| Inspector (Phase 1b) | Rich terminal metrics + zone comparison |
| Geometry (Phase 2) | Box rooms/corridors; inward walls; planar UVs |
| Elevation (Phase 2.5) | Multi-level layout; ramp & staircase corridors |
| Web app | FastAPI + Vite/Three.js; generate + first-person walk + overlays |
| Organic caves | SDF + marching cubes; noise-roughened walls; multi-lobe chambers; winding tunnels |
| Walkable floors + features | Flat-bottomed domes; stalactites/stalagmites/pillars |
| Outdoor terrain | Heightfield + erosion; walkable rolling hills |
| Textures | Procedural seamless (no API) + AI provider drop-in |
| Prompt planning (Phase 3) | Rule planner (no API) + LLM drop-in; expand → ZoneSpec |
| Classic–PoP profiles | Analyzer reads s3d/WLD; profiles from Guk/Sebilis/Faydark… |
| Theme-accurate scale | Room size from measured per-theme floor_area |
| TinyKeep layout | Scatter → separate → Delaunay → MST + loops → graph elevation |
| Pacing | Graph-derived roles (entrance/hub/climax/deadend) + depth; biased geometry & lighting |
| Gating | Optional lock-and-key suggestions, solvability-guaranteed |
| Top-down map | SVG floor-plan sidecar + web modal |
| Staircase fix | L-shaped corridors meet both wall openings; stairs flush at both landings |
| Cave connectivity fix | Tunnels join chambers into one watertight cave; floor winding fixed (no see-through); noise specks removed |
| Acceptance checklist | `docs/ACCEPTANCE.md` — manual UAT for validating major changes |

---

## Next — Phase 4: Refinement (highest priority)

The phase that turns a one-shot generator into an iterative tool.

- [ ] **Iterative chat loop** — refine an existing zone with follow-up prompts
      ("make the entrance wider", "add a water pool to the north") instead of
      regenerating from scratch. Needs: a session/zone-state concept server-side,
      a diff-style prompt interpretation, and a way to carry the seed/spec forward.
- [ ] **Partial regeneration** — re-run only changed rooms/textures, not the whole
      zone, so iteration is fast.
- [ ] **EQEmu SQL export** — zone records, spawn points, and door/key rows. A
      `GateSpec` maps to a `doors` row (`lock_x/y/z` → position, `corridor_id` →
      the opening, key → `keyitem`). This is what makes a generated zone playable.

---

## Design work captured, not yet built

- [ ] **Doorway-fit for gates** — catalogue the RoF2 door models used for doorways
      and their world-space footprints by theme (swinging wood/stone, portcullis,
      double doors, archway frames), then snap gated corridor openings to a chosen
      door type and record the model name on `GateSpec`. Prerequisite for a
      meaningful door export. (See README "Doors are records, not geometry".)
- [ ] **Water & mixed-environment zones**
  - [ ] Outdoor + water: a water plane at fixed Z, terrain sloped beneath it for a
        shoreline/lakebed, and an `AWT_` region so the client treats it as swimmable.
        Terrain backend needs a "water level" + shoreline shaping.
  - [ ] Cave-mouth-in-hillside: compose the SDF cave + heightfield terrain backends
        into one TER. Strongest argument for unifying both onto a single
        density-field representation (terrain as an SDF too).
- [ ] **Outdoor rooms as real places** — outdoor "rooms" currently only set terrain
      bounds; make them clearings, lookouts, etc.
- [ ] **Procedural normal maps** — textures are diffuse-only; real zones use the
      `e_TextureNormal0` material slot. No-API, high visual impact.
- [ ] **Content / semantic layer** — rooms are empty shells; give them semantic
      types + shared themes so a zone reads as a coherent place, realized through
      the existing pipeline (Version A: model supplies intent, deterministic
      rules realize it). No-new-art first slice = themes, region volumes,
      lighting mood, shape bias, spawn/encounter intent as data. See the design
      note "Content / semantic layer" below; pairs with the SQL export.

---

## Known issues / smaller fixes

- [ ] Style profiles for `city` and `cave` are thin (3–4 zones) — expand once more
      zone names are identified.
- [ ] Light-density stat reads 0 in profiles (most dungeon references use embedded
      MOD placement without ZON lights). Accurate, not a bug — but worth a note so
      it isn't "fixed" by mistake.
- [ ] Inspector ASCII bbox diagram doesn't render Z height — add a side-elevation view.
- [ ] Outdoor terrain is just the ground surface — no cliff walls, boulders, or
      vegetation yet.
- [ ] Web bundle is a single ~570 kB chunk (Vite warns > 500 kB). Cosmetic; could
      code-split Three.js if it ever matters.

---

## Deliberately NOT doing (and why)

Recording these so they aren't re-proposed:

- **Cave mesh decimation** — quadric decimation collapses the flat walkable floor
  into a few steep triangles. Poly count is controlled via `voxel` size instead.
- **Multi-key gating models (fragments / master key)** — the requested case was
  *independent* locks, which the N-separate-gates model already covers.
- **Baking doors into the `.ter`** — a door welded into the mesh is a door-shaped
  wall that can't open. Doors are runtime records (EQEmu `doors` table), produced
  by the SQL export, dropped into the open corridor gap.
- **Full Dormans mission-graph grammar** — EQ gates by depth/danger, not Zelda-style
  lock chains. We adopted only the solvability-invariant idea for gating.

---

## Phase status

| Phase | Description | Status |
|-------|-------------|--------|
| **0** | Zone analyzer — extract style profiles from RoF2 install | ✅ Done |
| **1** | Core I/O — PFS reader/writer, TER/ZON binary serialisers | ✅ Done |
| **1b** | Zone inspector — rich terminal metrics + profile comparison | ✅ Done |
| **2** | Procedural geometry — rooms, corridors, lighting, regions | ✅ Done |
| **2.5** | Elevation — multi-level layout, ramp & staircase corridors | ✅ Done |
| **web** | Browser app — dropdown generate + first-person walk + overlays | ✅ Done |
| **organic** | Cave geometry — SDF + marching cubes, noise-roughened walls | ✅ Done |
| **organic+** | Walkable floors + natural features (stalactites/pillars) | ✅ Done |
| **terrain** | Outdoor heightfield terrain — eroded, walkable rolling hills | ✅ Done |
| **textures** | Procedural seamless textures (no API) + AI provider drop-in | ✅ Done |
| **3** | Prompt-driven generation — rule planner (no API) + LLM drop-in | ✅ Done |
| **layout** | TinyKeep room-graph — scatter/separate/Delaunay/MST + loops | ✅ Done |
| **pacing** | Room roles & depth — entrance/hub/dead-end/climax, biased geometry & lighting | ✅ Done |
| **gating** | Lock-and-key suggestions (optional, keyed dungeons), solvability-guaranteed | ✅ Done |
| **4** | Refinement — iterative chat loop, partial regen, SQL export | ⏳ Next |

---

## Completed-work detail

Narrative record of what each area delivered and the decisions baked into it.

### Phase 0 — Zone analyzer

Reads any `.eqg`/`.s3d` zone from a RoF2 install and extracts measurable style
metrics: bounding dimensions, polygon density, material/shader counts, light
density, region-type distribution, and whole-zone floor area. Profiles are built
from authentic **Classic–PoP** zones (the default target era), read via the WLD
reader, and stored in `styles/`.

| Theme | Reference zones | Ceiling (mean) | Edge median | Materials |
|-------|-----------------|----------------|-------------|-----------|
| `dungeon` | Befallen, Sol A/B, Najena, Sebilis, Chardok, Velketor, Paw, Guk | 303 u | **12.4 u** | 102 |
| `outdoor` | Greater Faydark, Karanas, Oasis, Feerrott, Burning Woods, E. Wastes | 1103 u | 75 u (wide) | 52 |
| `city` | Qeynos, Freeport, Felwithe, Rivervale, Cabilis, Neriak | 403 u | **11.2 u** | 117 |
| `cave` | Crushbone, Blackburrow, Runnyeye, Cazic-Thule, Kedge, Guk, Warrens | 474 u | **14.1 u** | 116 |

Interior themes cluster at ~11–14 u median triangle edge — the authentic
Classic–PoP resolution the generator targets (cave default `voxel=12` ≈ 12 u).

**Theme-accurate scale.** Profiles also record whole-zone footprint: outdoor
zones average **~94M u²** of floor vs **~2M u²** indoor — roughly **40× larger**.
`LayoutGenerator` derives room size from each theme's measured `floor_area`
divided across room count, so outdoor zones are correctly vast and dungeons
correctly tight. Ceiling heights track the measured per-theme means.

### Phase 1 — Core I/O

- **`core/pfs.py`** — full PFS read/write. EQ big-endian CRC32 (`poly
  0x04C11DB7`, null-terminated, case-sensitive; ref `EQEmu/zone-utilities
  src/common/pfs_crc.cpp`). Multi-chunk deflate (RoF2 name blocks 35KB+).
  Validated: 1340/1340 filenames resolve in `broodlands.eqg`.
- **`core/ter.py`** — TER/MOD terrain serialiser (`EQGT`); materials, v2/v3
  vertices, polygon flags.
- **`core/zon.py`** — ZON placement serialiser (`EQGZ`); models, object
  instances (EQ heading unit conversion), region volumes, point lights.
- **`core/eqg.py`** — high-level assembler: TER + ZON + DDS → `.eqg`, plus GLB
  export for browser preview.
- **`core/wld.py`** — Classic–PoP `.s3d`/WLD geometry reader (0x36 meshes).

### Phase 1b — Zone inspector

`analyzer/inspect.py` — rich terminal metrics vs. the style profile (geometry
table, per-metric ✓/⚠ vs profile range, materials, lights/regions, texture list,
ASCII bbox diagram) and a side-by-side `--compare` of two zones. Metric fixes:
UV scale uses median of 99th-pct-clipped values; ZON search tries any `.zon`;
`has_zon` flag added (many RoF2 dungeons use embedded MOD placement).

### Phase 2 / 2.5 — Procedural geometry + elevation

Box backend: hollow rooms + corridors with inward-facing walls, planar UVs,
material resolution. Elevation is a generator feature (EQG collision is
per-triangle via the `0x01` flag — confirmed in `azone/map.cpp::CompileEQG` —
no BSP needed). Corridors ramp or build staircases between differing floor
heights. Corridors bend into an **L-shape** when the two wall openings aren't
collinear, and staircases sit flush at both landings (fixes a floating-stairs
bug).

### Organic caves + features

`cave` theme uses a density-field backend: solid rock → carve chambers
(irregular multi-lobe blobs) and tunnels (winding capsule chains) → FBM wall
noise → marching cubes → single watertight mesh. Floors stay walkable
(flat-bottomed domes, floor-tapered one-sided noise, re-intersected with the
floor plane after blending). Features (stalactites/stalagmites/pillars) grow
into the field before meshing so they fuse with the rock. Noise is fully
vectorised numpy (~27s → ~1s); features use localized SDFs (97s → 8s big caves).

### Outdoor terrain

`outdoor` theme: FBM hills → thermal erosion → walkable-gradient cap (≈100%
under 40°) → triangulated ground mesh with gradient normals.

### Textures

Provider abstraction: `ProceduralProvider` (default, no API — layered tileable
value noise, seamless, ~20ms) and `AIProvider` (optional, OpenAI/Stability, falls
back to procedural on any failure). Factory auto-selects, caches, honours
`EQ_S3D_TEXTURE_PROVIDER`. Diffuse-only for now (normal maps are a known gap).

### Web app

FastAPI backend (`server/app.py`, fresh random seed per call, serves GLB +
`.zone.json` sidecar + front-end). Vite/TS/Three.js first-person viewer
(`web/`): WASD at EQ scale, pointer-lock look, toggleable overlays
(wire/lights/regions/gates), top-down SVG map modal, live metrics panel.
Single-command dev launcher (`web/dev.mjs`).

### Prompt-driven generation

`RulePlanner` (default, keyword/heuristic, no API) and `LLMPlanner` (optional,
OpenAI/Anthropic, JSON output grounded in style profiles, falls back to rule).
`expand.plan_to_spec` drives the same `LayoutGenerator` the dropdowns use.

### Layout + pacing + gating

TinyKeep spatial layout (scatter → separate → Delaunay → MST + ~12% loop edges →
graph elevation → wall-to-wall corridors). Pacing analyses the graph for roles
(entrance/hub/climax/deadend) and depth, biasing geometry and lighting so the
progression is visible. Gating optionally places lock-and-key *suggestions* on
deep tree edges with keys reachable earlier (solvability guaranteed). Pacing and
gating ride in the sidecar — advisory metadata, never baked into geometry.

---

## Design notes & rationale

### Geometric fidelity by era

Generated geometry should sit at the resolution the original artists worked at —
not smoother (reads too modern) nor coarser. Key metric: **median triangle edge
length** (world units), measured from real zones. Format boundary is **Gates of
Discord (2003)**: Classic → PoP ship as `.s3d`/WLD; GoD onward as `.eqg`.

| Era | Format | Median edge (u) | Median polys |
|-----|--------|-----------------|--------------|
| Classic (1999) | s3d | **13.1** | 22.6k |
| Kunark (2000) | s3d | **14.1** | 39.3k |
| Velious (2000) | s3d | 49.3 (big open zones) | 41.6k |
| Luclin (2001) | s3d | 8.0 (finer architecture) | 57.8k |
| PoP (2002) | s3d | **12.2** | 105k |
| GoD/OoW (2003–4) | eqg | 13.2 | 166k |
| DoN/DoDH (2005) | eqg | 5.8 | 148k |
| TBS/SoF (2007) | eqg | 15.8 | 50k |
| SoD/UF (2008–9) | eqg | 18.4 | 61k |
| HoT/VoA (2010–11) | eqg | 20.4 | 213k |
| RoF (2012) | eqg | 5.8 | 71k |

The iconic Classic/Kunark/PoP look clusters at ~12–14u median edge — the default
target (`voxel=12` ≈ 12u, confirmed). Fidelity didn't evolve monotonically; it
oscillated with art teams, tools, and zone type.

### Room-graph composition (TinyKeep + pacing + gating)

The room-graph is the zone's abstract floor-plan (rooms = nodes, corridors =
edges) that every backend realises into 3D. The naive random walk was replaced
with the TinyKeep spatial layout above, fixing overlap/tangle/linearity. Pacing
assigns roles + depth; gating adds optional lock-and-key suggestions. All three
geometry backends consume the layout unchanged.

### Doors are records, not geometry — openings must fit a door model

A functional EQ door is a separate record (EQEmu `doors` table) referencing an
animated door model, with position/heading/open-type/`keyitem`; the server drives
open-close and gatekeeping. Expected to be consistent across EQG and classic
s3d/WLD (both feed the EQEmu door system); the per-format door-model lookup needs
verifying against our readers before writing the export.

- **Never bake a door into the `.ter`** — it becomes a door-shaped wall that
  can't open. Corridors stay open gaps; a `GateSpec` becomes a real door only in
  the SQL export (`lock_x/y/z` → position, `corridor_id` → opening, key →
  `keyitem`).
- **The opening is the constraint** — a gated corridor's width/height must fit a
  standard EQ door. Follow-up: catalogue RoF2 doorway models + footprints by
  theme, then snap gated openings to a chosen door type and record its model name
  on the `GateSpec`.

### Water and mixed-environment zones

- **Outdoor + water** — water plane at fixed Z, terrain sloped beneath it for a
  shoreline/lakebed, an `AWT_` region so the client treats it as swimmable.
  Terrain backend needs a water level + shoreline shaping.
- **Cave-mouth-in-hillside** — compose SDF cave + heightfield terrain into one
  TER. Strongest argument for unifying both onto a single density-field
  representation (terrain as an SDF too).

### Content / semantic layer — making rooms *interesting* (candidate for after Phase 4)

So far the generator solves **spatial structure**: where rooms are, how they
connect, that they're navigable and enclosed. It does almost nothing about
**content** — what makes a room a memorable *place* rather than an empty shell.
These are different problems and should stay separated.

**Two separate problems hiding under "interesting rooms":**

1. **Semantic content** — what a room *is* and *means*: a flooded crypt with an
   submerged altar, collapsed mine shaft, guard barracks, throne dais. Props,
   set dressing, encounter/spawn intent, loot, and a *theme* that ties rooms
   into a small narrative (barracks → prison → ritual chamber). Almost entirely
   missing today.
2. **Geometric uniqueness** — the room's shape being distinctive. We have a
   little (pacing biases size, caves vary) but it's shallow.

"Rooms as nodes that share themes" is problem #1, and it lives at the
**ZoneSpec / graph level, not the mesh level** — which decides where ML fits.

**Where a model helps — Version A (recommended):** a model (most likely the
existing `LLMPlanner`, extended) produces a *richer structured ZoneSpec* — per-
room semantic type + theme + intent ("flooded ritual chamber, floor -40, raised
altar platform, water region in the lower third, 4 braziers, boss on the dais").
Our deterministic pipeline already converts structured descriptions into
EQ-accurate, navigable, enclosed geometry. The model supplies *creativity and
semantics*; the pipeline keeps the hard-constraint guarantees. No training data
needed — it's a design/language task on a general model.

**Where a model does NOT help — Version B (avoid):** a model generates the
actual 3D *mesh* of a room and we "restyle" it to look EQ. 3D mesh style-transfer
isn't a drop-in solved thing; you'd get wrong-resolution, hole-ridden meshes you
must remesh/repair/retexture anyway, and there's no corpus to train a room-mesh
generator on. Repairing back to our guarantees throws away most of what the model
gave you.

**Key insight:** "convert generated rooms to the EQ look" assumes the look lives
in the geometry and must be transferred. But from our measurements the EQ look
lives mostly in **resolution, proportion, palette, and texture** — which the
style profiles and backends already enforce. So we don't need to restyle a mesh;
we need to feed richer *semantic intent* into a pipeline that already produces
the look. The model never needs to know what EQ looks like.

**Proposed layer (between layout and geometry):**
- Assign each room a **semantic type + theme**, coherent with neighbours, so the
  progression reads as a small story (graph-labelling on the pacing graph we have).
- Each room type carries **content rules** → expand into ZoneSpec elements
  (region volumes, lights, elevation/shape bias) and eventually MOD placements +
  EQEmu spawn/loot/door data via the same deterministic realization.
- The (LLM) planner proposes theme assignment + per-room intent from the prompt;
  deterministic rules realize it as valid, era-accurate geometry/placement.
- Lines up with the planned EQEmu SQL export — content and server-side data are
  the same layer.

**No-new-art first slice:** props/set-dressing need actual MOD models to place,
which we don't generate (generating EQ-authentic props is its own hard problem;
likely reference existing EQ object models, cf. the door-model note). So start
with the parts needing zero new art: semantic room themes, region volumes
(water/lava), lighting mood, per-theme elevation/shape bias, and spawn/encounter
intent carried as data for the SQL export.

### Should we train a bespoke model instead? (decision: no, for the core)

Recorded so the question has a durable answer. Training a from-scratch 3D-mesh
generator for zones is the wrong tool here:
- **Data regime** — only a few hundred real EQ zones exist, one narrow art
  style, no pretrained base to fine-tune. Far too little for 3D generation.
- **Hard constraints** — navigable floors, watertight enclosure, reachable
  rooms, solvable gating are discrete global pass/fail properties. Generative
  mesh models produce plausible-but-leaky output (holes, non-manifold edges,
  unreachable pockets — the exact bugs we fix deterministically). You'd bolt the
  repair passes back on anyway.
- **Controllability** — prompt-driven iteration ("make the entrance wider") is
  trivial with explicit parametric knobs, hard to steer in a mesh generator.
- **Format** — output still has to become valid `.ter`/`.zon`/PFS with
  per-triangle collision; the model doesn't help with the part we've solved.

Where ML *does* fit, in priority: (1) richer LLM planning / the semantic layer
above; (2) a lightweight learned "EQ-ness" critic that scores a generated zone
against real-zone feature distributions (discriminative, modest data) — only if
"does this *feel* like EQ?" becomes the bottleneck; (3) learned textures /
normal maps (the AI texture provider is already a drop-in slot). Keep the
procedural spine; push ML into planning/semantics and optionally textures.
