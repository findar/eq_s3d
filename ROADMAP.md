# Roadmap & Open Items

The authoritative list of what's done, what's next, and known gaps. The README
carries the narrative "what it does / how it works"; this file is the tracker.
Keep it in sync when work lands (check items off, move them, note the commit).

Last updated: content layer Step 1 landed, 164 tests passing. See "Next".

---

## ▶ Pick up here (next session)

**Cave generation is shelved for now.** Despite the automated connectivity tests
passing, a human 3D check still shows caves rendering as isolated solid blobs
(disconnected chambers, stray region volumes). The automated tests and the
rendered result disagree — a known gap. Rather than keep chasing the current
cave backend, we're **parking it** and will rebuild it later with a better
architecture (see "Cave = cavified dungeon layout" below). The `cave` theme is
not trustworthy until then; focus on the **dungeon (box) backend**, which works.

**Content layer — Step 1 (single-district themes) is DONE.** Dungeon rooms now
get a semantic type from an archetype × race × elemental-tint theme (realised
into shape/region/light/palette; props/encounters/boss carried as suggestions).
See "Next" #1 and the design in `docs/RESEARCH.md`.

**Suggested next step:** the content layer's **Step 2 — districts** (multi-area
zones): partition the room graph into contiguous sub-themed districts
(auto-split large zones, with an off switch), per-district climaxes, and gated
thresholds between districts. Design + decisions are in `docs/RESEARCH.md`
("Multi-area zones — districts").

**Priorities:** content layer Step 2 (districts) → refinement → SQL export →
(revisit) cave rebuild. Re-sequencing reasoning is under "Next".

**Needs a 3D eyeball (Step 1):** the structural tests pass, but per the cave
lesson that is necessary-not-sufficient. Before Step 2, confirm in the viewer
that themed rooms read as distinct places — processional throne/ritual halls,
tight prison cells, sunken flooded rooms with water regions sitting in the
floor, forge rooms glowing with lava — and that the per-room palette variants
and lighting mood are visibly different between themes. See `docs/ACCEPTANCE.md`.

**Validate major changes** with the acceptance checklist in
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md). Proc-gen approach investigations and
their verdicts are in [`docs/RESEARCH.md`](docs/RESEARCH.md).

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
| Content layer — Step 1 | Dungeon semantic themes: archetype × race × tint; per-room type, shape/region/light/palette realization; props/encounter/boss as suggestions; surfaced in viewer panel + top-down map |

---

## Next — ordered priorities

Rationale for this order: the north-star is "indistinguishable from hand-crafted"
with the layout as a starting point for a manual pass. Making rooms *theme-coherent*
moves that needle most; iterative refinement is usability polish worth doing once
there's richer output to iterate on; the SQL export is the "now make it playable"
capstone that consumes the content layer's suggestion data. Manual validation
passes (`docs/ACCEPTANCE.md`) are good enough to vet designs until then, so the
export sits last.

### 1. Content / semantic layer — theme-conforming rooms + suggestions

Give each room a semantic **type + theme**, assigned coherently across the graph
so the zone reads as a place with a progression. Scope is **no new art**. Design,
theme vocabulary, and the archetype × race × tint + districts model are in
`docs/RESEARCH.md` ("Content / semantic layer — dungeon theme vocabulary &
districts"). Split into two steps:

- [x] **Step 1 — single-district themes (DONE).** A room gets a semantic type
  from a zone **archetype** (fortress / war_city / warren / temple / tomb /
  wizard_lair / corrupted_sanctum / mine_delve / sunken_ruin / lava_forge /
  ice_keep), scaled by an inhabiting **race** (global size multiplier) with an
  optional elemental **tint** (lava/ice/water). Realized into geometry — shape /
  proportion bias, `AWT_`/`ALV_` region volumes, lighting mood, elevation
  character, per-theme palette (material variants). Props / encounter intent /
  boss are carried as **suggestions** (RoomSpec fields → sidecar + map + viewer,
  for the eventual SQL export). The rule planner detects archetype/race/tint
  keywords; the LLM planner can propose them (schema extended). Code:
  `generators/semantics.py`, wired into `generators/layout.py::generate`.
  *Known gap: race scale values are relative placeholders pending real EQ model
  dimensions (see Known issues).*
- [ ] **Step 2 — districts (NEXT).** Partition the room graph into 1–3
  contiguous **districts**, each its own sub-theme, joined at hubs / gated
  thresholds — so a zone can be several places at once (live vs. dead side,
  fortress + warren). Auto-split large zones (≥8 → 2, ≥14 → 3) with an off
  switch; **per-district climaxes** (multiple boss rooms allowed); a district
  **relationship** tag (sequential / factional / abandoned-vs-active). Renders
  district boundaries on the map/viewer. `RoomSpec.district` and a
  `ZoneSpec.districts` list already exist as placeholders.

- **Explicitly NOT doing:** placing prop MODs. A room *is* a theme-conforming
  empty space with written suggestions, not furnished geometry.

### 2. Iterative refinement

Worth building once there's content-rich output to refine.

- [ ] **Iterative chat loop** — refine an existing zone with follow-up prompts
      ("make the entrance wider", "add a water pool to the north") instead of
      regenerating from scratch. Needs: a session/zone-state concept server-side,
      a diff-style prompt interpretation, and a way to carry the seed/spec forward.
- [ ] **Partial regeneration** — re-run only changed rooms/textures, not the whole
      zone, so iteration is fast.

### 3. EQEmu SQL export (capstone — makes a zone playable)

- [ ] Zone records, spawn points, and door/key rows. A `GateSpec` maps to a
      `doors` row (`lock_x/y/z` → position, `corridor_id` → the opening, key →
      `keyitem`); the content layer's spawn/encounter suggestions become spawn
      and loot rows. Deferred to last: empty shells aren't worth standing up on a
      server, and manual validation covers design checks until then. This is also
      where to add a real **in-engine validation loop** (load one generated zone
      on an EQEmu server) so quality isn't judged only by our own reader/viewer.

---

## Design work captured, not yet built

(Opportunistic — slot in around the ordered priorities above. Normal maps in
particular are a cheap, high-impact quick win.)

- [ ] **Cave rebuild — "cavify the dungeon layout"** *(shelved; revisit after the
      ordered priorities)* — scrap the current cave backend's independent spatial
      derivation; instead take the box/dungeon layout (already correct + connected)
      and apply an organic-styling transform. Fixes the disconnected-blob class of
      bug by construction. The `cave` theme is untrustworthy until this lands —
      use `dungeon`. See the design note "Cave = cavified dungeon layout".
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
- [ ] **Doorway-fit** also gates a real door export (listed above); it depends on
      the catalogue of RoF2 door models.

---

## Known issues / smaller fixes

- [ ] **Cave theme broken in 3D despite passing tests** — chambers render as
      isolated solid blobs with stray region volumes, even though the automated
      connectivity tests (`TestCaveConnectivity`) report a single watertight
      component. The tests and the rendered result disagree, so the tests are NOT
      a faithful acceptance gate for caves — trust the 3D viewer. Being addressed
      by the "cavify the dungeon layout" rebuild, not a patch. Use `dungeon` until
      then. (This mismatch is itself a lesson: automated structural checks can
      pass while the viewer shows something wrong — validate major geometry
      changes in 3D per `docs/ACCEPTANCE.md`.)
- [ ] **Race scale values are relative placeholders** — the content layer's
      per-race size multipliers (`giant` 2.2×, `froglok` 0.9×, …, in
      `generators/semantics.py::RACE_SCALE`) are tuned-by-feel, not measured.
      Real per-race limits (doorway clearance, headroom) should come from EQ
      model bounding boxes, which we don't have yet; the RoF2 install at
      `F:\everquest_rof2` could be mined for model bounds the way the
      era-fidelity triangle-edge table was. Until then they're a tunable knob.
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
- **Grid + rule-tile rooms (Labyrinth "Blueprints")** — grid-snapped rooms whose
  shape is chosen from the neighbour pattern read as modern roguelike (Isaac /
  Gungeon), the opposite of hand-crafted EQ sprawl. We already use the stronger
  non-grid choices (TinyKeep over Drunkard's-Walk+A\*). See `docs/RESEARCH.md`.

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
| **organic** | Cave geometry — SDF + marching cubes | ⚠ Shelved (broken in 3D; rebuild as cavified dungeon layout) |
| **organic+** | Walkable floors + natural features (stalactites/pillars) | ✅ Done |
| **terrain** | Outdoor heightfield terrain — eroded, walkable rolling hills | ✅ Done |
| **textures** | Procedural seamless textures (no API) + AI provider drop-in | ✅ Done |
| **3** | Prompt-driven generation — rule planner (no API) + LLM drop-in | ✅ Done |
| **layout** | TinyKeep room-graph — scatter/separate/Delaunay/MST + loops | ✅ Done |
| **pacing** | Room roles & depth — entrance/hub/dead-end/climax, biased geometry & lighting | ✅ Done |
| **gating** | Lock-and-key suggestions (optional, keyed dungeons), solvability-guaranteed | ✅ Done |
| **content** | Theme-conforming rooms + suggestions (no prop placement) | ◑ Step 1 done (single-district themes); Step 2 (districts) next |
| **refine** | Iterative chat loop + partial regeneration | ⏳ |
| **export** | EQEmu SQL export + in-engine validation (capstone) | ⏳ |

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

### Cave = cavified dungeon layout (planned rebuild)

The current cave backend re-derives its own spatial structure (chambers from
rooms, tunnels from corridors, with fragile endpoint-matching), and it keeps
rendering as disconnected blobs in 3D even though the connectivity tests pass —
the tests and the rendered result disagree, which means the backend is building
geometry our analysis doesn't faithfully capture. Rather than keep patching it,
the plan is to **rebuild the cave as a transform of the dungeon layout**:

1. Generate the layout with the **box/dungeon backend**, which already produces a
   correct, connected, navigable set of rooms + corridors that meet their
   openings. This is the single source of truth for connectivity.
2. **"Cavify"** that known-good geometry as a post-process: round box rooms into
   organic chambers, convert corridors into winding tunnels, roughen with noise —
   while preserving the connectivity that already works.

Connectivity is thus established once, in the backend that gets it right; the
cave becomes a styling pass over validated geometry instead of an independent
re-derivation. This should eliminate the disconnected-chamber class of bug by
construction. Open design question: whether to cavify at the mesh level (deform
the box mesh) or re-voxelise the box layout into an SDF and re-mesh — the latter
is closer to what we have and composes with the terrain-as-SDF idea below.

Until this rebuild lands, the `cave` theme is not trustworthy; use `dungeon`.

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
