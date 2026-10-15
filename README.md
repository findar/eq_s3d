# eq_s3d — Agentic EverQuest Zone Generator

Generate EverQuest EQG zone files from natural language prompts, targeting the **RoF2 client**.

> **Status**: Lock-and-key gating ✅ — optional keyed dungeons (Chardok-style) with solvability-guaranteed layout, on top of the TinyKeep spatial layout + pacing. Open dungeons (Guk-style) remain the default.

---

## What It Does

Generate playable EverQuest `.eqg` zone files and walk through them in the browser —
no 3D modelling required. The tool handles geometry, textures, lighting, and packaging.

**Today** (web app, dropdown-driven): pick a theme, room count, and elevation, hit
Generate, and walk through a freshly built multi-level zone in a first-person
browser viewer. Every generation uses a random seed, so the same inputs always
produce a different zone.

```bash
cd web && npm install && npm run dev     # one command starts everything
#    → open http://localhost:5173
```

**The end goal** (Phase 3) is prompt-driven generation on the same pipeline:

```
> generate a dark stone dungeon with a lava river and torch lighting
> make the entrance corridor wider
> add a second room to the north with a water pool
```

The `/api/generate` endpoint already accepts a `prompt` field (currently ignored),
so Phase 3 is additive: add a prompt box to the UI and an LLM planner behind the
endpoint, with no change to the geometry/packaging pipeline underneath.

---

## Architecture

```
core/       — Binary I/O: PFS container, TER terrain, ZON placement, WLD reader
  └─ wld.py         — Classic–PoP .s3d/WLD geometry reader (0x36 meshes)
analyzer/   — Extract style metrics from existing EQ zones
  ├─ extractor.py   — per-zone metric extraction
  ├─ style_builder.py — build style profile JSONs from a corpus
  └─ inspect.py     — rich terminal inspector + zone comparator
generators/ — Procedural geometry, lighting, region volumes
  ├─ zone_spec.py   — serialisable ZoneSpec (the IR)
  ├─ geometry.py    — MeshBuilder: box rooms, corridors, ramps, stairs
  ├─ layout.py      — LayoutGenerator: seedable 3D room-graph
  ├─ textures/      — texture providers (procedural default, AI drop-in)
  │   ├─ procedural.py — layered tileable noise → stone/rock/dirt/grass
  │   ├─ ai.py       — reference image-API provider (optional, needs key)
  │   ├─ dds.py      — DDS encoder + seamless-tiling helper
  │   └─ factory.py  — provider selection, caching, fallback
  ├─ field/         — organic (SDF + marching cubes) geometry
  │   ├─ sdf.py      — density-field primitives (sphere/capsule/cone/dome) + carve
  │   ├─ noise.py    — fast vectorised FBM value noise (wall roughness)
  │   ├─ cave.py     — carve chambers+tunnels, walkable flat floors
  │   ├─ features.py — stalactites / stalagmites / pillars (surface-aware)
  │   ├─ terrain.py  — heightfield + erosion → walkable rolling hills
  │   └─ mesh.py     — marching cubes → TerFile + decimation
  └─ builder.py     — ZoneBuilder: routes box vs organic backend → .eqg + .glb
server/     — FastAPI backend wrapping the generators for the web UI
web/        — Vite + TypeScript browser app (Three.js first-person viewer)
viewer/     — Legacy standalone Flask GLB preview (superseded by web/)
ai/         — prompt → ZoneSpec planning
  ├─ schema.py      — ZonePlan (the compact plan a planner produces)
  ├─ rule_planner.py — keyword/heuristic planner (no-API default)
  ├─ llm_planner.py — LLM planner (OpenAI/Anthropic drop-in, optional)
  ├─ expand.py      — ZonePlan → ZoneSpec via LayoutGenerator
  └─ planner.py     — factory: LLM if key else rule, with fallback
styles/     — Empirically-derived style profiles per zone theme
```

**Generation pipeline**:
```
User Prompt → AI Planner → ZoneSpec JSON
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
          Geometry        Textures         Lights/Regions
          (TER file)      (DDS files)      (ZON file)
                └──────────────┼──────────────┘
                               ▼
                     PFS packer → .eqg  +  .glb (browser preview)
```

---

## Setup

```bash
git clone https://github.com/yourname/eq_s3d.git
cd eq_s3d

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set EQ_PATH to your RoF2 install and your AI API keys
```

**Requirements**: Python 3.11+, a legally-obtained RoF2 client install (for style analysis only — no game assets are distributed).

---

## Usage

### Inspect a zone and validate metrics

```bash
# Single zone inspection with style profile comparison
python -m analyzer.inspect F:/everquest_rof2/bertoxtemple.eqg --theme dungeon

# Compare two zones side-by-side
python -m analyzer.inspect F:/everquest_rof2/bertoxtemple.eqg --compare F:/everquest_rof2/dreadspire.eqg
```

### Build style profiles from your EQ install (do this once)

```bash
python -m analyzer.style_builder --eq-path "F:/everquest_rof2" --all
```

This reads geometry data from reference zones and writes empirical style profiles
to `styles/`. Pre-built profiles for RoF2 are included in this repo.

### Web app — generate and walk zones in the browser ⭐

**One command** starts everything. The Node launcher spawns the Python backend,
waits for it to be healthy, then starts Vite — and one Ctrl+C stops both.

```bash
cd web && npm install   # first time only
npm run dev
#    → open http://localhost:5173
```

Backend logs appear prefixed `[api]`, the front-end `[web]`.

Production build (served entirely by the Python backend, no Node needed to run):

```bash
cd web && npm run build
python -m uvicorn server.app:app --port 8000
#    → open http://localhost:8000
```

Advanced: `npm run dev:web` runs only Vite (if you prefer to start the backend
yourself with `python -m uvicorn server.app:app --host 127.0.0.1 --port 8000`).

Pick a theme and room count from the dropdowns and hit **Generate**. Each
generation uses a fresh random seed, so the same inputs always produce a
different zone. Click the viewport to capture the mouse, then walk with WASD
(Shift to sprint, Q/E for down/up, R to reset). Toggle wireframe, light, and
region overlays in the side panel.

> Generation is driven by the theme/rooms/elevation controls today. A text-prompt
> box plugs into the same endpoint in Phase 3.

### Generate a zone from the CLI

```bash
python main.py generate myrealm --theme dungeon --rooms 5 --seed 42
python main.py generate myrealm --theme dungeon --rooms 5 --preview   # legacy Flask viewer
```

Output lands in `output/`: `myrealm.eqg` (for the client), `myrealm.glb`
(browser preview), `myrealm.zone.json` (lights/regions sidecar), and
`myrealm.json` (the editable ZoneSpec). Validate against the style profile:

```bash
python -m analyzer.inspect output/myrealm.eqg --theme dungeon
```

### Run the test suite

```bash
python -m pytest tests/ -v
# 49 passed
```

---

## Project Phases

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
| **gating** | Lock-and-key progression (optional, keyed dungeons), solvability-guaranteed | ✅ Done |
| **4** | Refinement — iterative chat loop, partial regen, SQL export | ⏳ Next |

---

## What's Done

### Phase 0 — Zone Analyzer ✅

Reads any `.eqg` archive from a RoF2 install and extracts measurable style metrics:
bounding dimensions, polygon density, material counts, shader usage, light density,
and region type distribution.

Style profiles are derived from authentic **Classic–PoP** zones (the default
target era), read via the WLD reader (stored in `styles/`):

| Theme | Reference zones | Ceiling (mean) | Edge median | Materials |
|-------|-----------------|----------------|-------------|-----------|
| `dungeon` | Befallen, Sol A/B, Najena, Sebilis, Chardok, Velketor, Paw, Guk | 303 u | **12.4 u** | 102 |
| `outdoor` | Greater Faydark, Karanas, Oasis, Feerrott, Burning Woods, E. Wastes | 1103 u | 75 u (wide) | 52 |
| `city` | Qeynos, Freeport, Felwithe, Rivervale, Cabilis, Neriak | 403 u | **11.2 u** | 117 |
| `cave` | Crushbone, Blackburrow, Runnyeye, Cazic-Thule, Kedge, Guk, Warrens | 474 u | **14.1 u** | 116 |

The interior themes cluster at ~11–14 u median triangle edge — the authentic
Classic–PoP resolution the generator targets (cave default `voxel=12` ≈ 12 u).
These profiles constrain the generator so output stays within real-zone bounds.

**Theme-accurate scale.** The profiles also record whole-zone footprint, and the
measurement is dramatic: outdoor zones average **~94M u²** of floor area vs **~2M u²**
for indoor zones — roughly **40× larger**. The `LayoutGenerator` now derives
room size from each theme's measured `floor_area` divided across the room count,
so a generated outdoor zone is correctly vast and a dungeon is correctly tight —
the same room count yields a ~7× larger room in `outdoor` than in `dungeon`.
Ceiling heights likewise track the measured per-theme means.

### Phase 1 — Core I/O ✅

**`core/pfs.py`** — Full PFS archive read/write.
- Correctly implements EQ's big-endian CRC32 (`poly 0x04C11DB7`, null-terminated,
  case-sensitive). Reference: `EQEmu/zone-utilities/src/common/pfs_crc.cpp`.
- Handles multi-chunk deflate streams (RoF2 name blocks can be 35KB+).
- Validated against real RoF2 archives: 1340/1340 filenames resolve in `broodlands.eqg`.

**`core/ter.py`** — TER/MOD terrain binary serialiser.
- Reads and writes EQG terrain files (`EQGT` magic).
- Full support for materials (string-table offsets, typed properties), v2 and v3 vertices,
  and polygon flags.

**`core/zon.py`** — ZON placement binary serialiser.
- Reads and writes EQG zone placement files (`EQGZ` magic).
- Handles model registration, object instances with EQ heading unit conversion,
  region volumes (water/lava/zoneline/PvP), and point lights.

**`core/eqg.py`** — High-level assembler: packs TER + ZON + DDS textures into a `.eqg` archive,
plus GLB export for browser preview.

**`viewer/`** — Self-contained Three.js first-person zone viewer. Served locally via Flask,
auto-reloads when a new GLB is written. WASD movement at EQ scale (6 units = 1 character height).

### Phase 1b — Zone Inspector ✅

**`analyzer/inspect.py`** — Rich terminal inspector for validating zone metrics against style profiles.

```
python -m analyzer.inspect F:/everquest_rof2/bertoxtemple.eqg --theme dungeon
```

Output includes:
- Geometry table: vertex/polygon counts, dimensions (u), floor area, polygon density
- Per-metric ✓/⚠ indicators vs. the style profile's min/max range
- Materials: count, texture filenames, shader names
- Lights & Regions: count, density, mean RGB, region type breakdown (water/lava/zoneline)
- Full texture list
- ASCII bounding-box diagram with scale

```
python -m analyzer.inspect zone_a.eqg --compare zone_b.eqg
```

Side-by-side delta comparison of any two zones — the foundation for comparing
generated zones against reference originals.

**Metric fixes made during investigation:**
- UV scale now uses **median of 99th-pct-clipped** values (terrain zones legitimately tile at 50–200+)
- ZON file search now tries any `.zon` in the archive (RoF2 names don't always match zone name)
- `has_zon` flag added to metrics — many RoF2 dungeons use embedded MOD placement without a ZON file
- Style profiles rebuilt from corrected extractor

---

### Phase 2 — Procedural Geometry ✅

The generator turns a `ZoneSpec` (structured, editable JSON) into a complete `.eqg`:

- **`generators/zone_spec.py`** — `ZoneSpec` dataclass: materials, rooms, corridors, lights, regions. Fully serialisable to/from JSON.
- **`generators/geometry.py`** — `MeshBuilder`: builds hollow box rooms and corridors with inward-facing walls, planar UV projection, and material resolution. Emits a `TerFile`.
- **`generators/layout.py`** — `LayoutGenerator`: seedable procedural room-graph layout. Walks rooms along a grid, connects them with corridors, opens facing walls, places theme-appropriate lights. Pulls target dimensions from the style profile.
- **`generators/textures.py`** — placeholder DDS generator (solid colour + noise). Phase 3 swaps this for AI image generation.
- **`generators/builder.py`** — `ZoneBuilder`: orchestrates geometry + placement + textures into a `.eqg` + `.glb`. Follows RoF2 convention (terrain stored as `ter_<zone>.ter`, referenced as ZON model[0]).

### Phase 2.5 — Elevation ✅

EQG zones are fully 3D — collision is derived per-triangle from the polygon's
`0x01` flag (confirmed in `EQEmu/zone-utilities azone/map.cpp::CompileEQG`), with
no BSP tree required. Real zones like Dreadspire are a single TER mesh spanning
10,560 units of vertical range. So verticality is a generator feature, not a
format limitation.

- **`CorridorSpec`** now carries `from_z` / `to_z` (with a `floor_z` back-compat alias) and a `steps` count.
- **`MeshBuilder`** builds **ramp** corridors (smooth slope between two heights) and **staircase** corridors (flat treads + vertical risers).
- **`LayoutGenerator`** does a 3D walk: rooms are placed at varying floor heights, and connecting corridors ramp or step between them.

```bash
python main.py generate towers --theme dungeon --rooms 8   # multi-level by default
```

Generated zones round-trip cleanly through our own reader and match the structural
layout of real RoF2 zones. The inspector compares them against the style profile:

```
python -m analyzer.inspect output/testdungeon.eqg --theme dungeon
  Ceiling Z   120 u ✓   (profile: 77–10560)
  Materials   3 ⚠       (profile: 18–83)   ← placeholder, Phase 3 adds variety
  Shader      MPLBump2UV ✓                 ← matches real dungeons
```

### Organic Cave Geometry ✅

The target is zones **indistinguishable from hand-crafted** — focused on *natural*
geometry (caves, hills, earthen walls, stalactites, pillars) rather than clean
architecture. Natural forms are irregular by definition, which is exactly where
procedural techniques excel: a noise-eroded cave wall and a hand-sculpted one have
no pattern to tell them apart.

The `cave` theme now uses a **density-field backend** instead of boxes:

1. Start with a solid block of rock (a 3D scalar field, positive = solid).
2. **Carve** the walkable volume — rooms become spherical chambers, corridors
   become capsule tunnels — pushing the field negative (air).
3. Add **FBM value noise** to the carved boundary so walls are lumpy and organic,
   not smooth tubes.
4. Extract the rock/air surface with **marching cubes** → a single watertight
   organic mesh, decimated to a sane poly count.

This maps perfectly onto EQG: collision is per-triangle (confirmed from
`azone/map.cpp`), so a dense organic mesh works exactly like a hand-made zone's.

```bash
python main.py generate grotto --theme cave --rooms 5
#   → ~40k-poly organic cave, generated in ~1 second
```

The noise is fully vectorised numpy (no per-voxel Python), bringing generation
from ~27s down to ~1s — fast enough for the interactive web loop.

**Walkable floors.** Characters have to navigate these zones, so chambers are
carved as flat-bottomed **domes** (sphere ∩ half-space) rather than full spheres,
and wall noise is **tapered to near-zero at the floor** and clamped one-sided
there so it raises gentle bumps but never digs pits. The result is a navigable
floor with natural undulation — not a flat disc, not a slippery bowl. (Mesh
decimation is deliberately off for caves: quadric decimation collapses the flat
floor into a few steep triangles, so poly count is controlled via voxel size.)

**Natural features.** `field/features.py` grows stalactites (ceiling cones),
stalagmites (floor cones), and pillars (floor-to-ceiling columns) into the carved
field *before* meshing, so they fuse with the rock as one continuous surface
rather than looking like placed props. Floor features are kept toward chamber
edges so the walkable core stays clear.

### Outdoor Terrain ✅

The `outdoor` theme uses a **heightfield** backend (`field/terrain.py`) — a
surface rather than a carved volume:

1. FBM noise generates rolling hills over a 2D grid.
2. **Thermal erosion** slumps steep slopes to a natural angle of repose, so
   ridges and valleys read as weathered rather than blobby noise.
3. A **walkable-gradient cap** relaxes any cell steeper than the max climbable
   grade, keeping the whole surface navigable (verified: ~100% under 40°).
4. The grid is triangulated into a ground mesh with gradient-derived normals.

```bash
python main.py generate meadow --theme outdoor --rooms 5
#   → eroded rolling hills sized to the zone footprint, fully walkable
```

### Texturing — Procedural Default + AI Drop-in ✅

Textures use a **provider abstraction** so the project needs no API key to look
good. Two providers:

- **`ProceduralProvider`** (default) — layered **tileable value noise** modulated
  by a base colour produces matte, muted stone / rock / dirt / grass surfaces
  anchored to EQ's palette. Seamless (an offset-and-blend pass kills edge seams),
  deterministic, ~20ms per texture, **zero external calls**.
- **`AIProvider`** (optional) — a reference image-API provider (OpenAI or
  Stability) that activates only when a key is set in `.env`. Prompts are anchored
  to the late-90s muted-fantasy-stone aesthetic. On any failure it falls back to
  procedural, so generation never breaks.

The factory auto-selects (AI if a key is present, else procedural), caches by
spec, and honours an `EQ_S3D_TEXTURE_PROVIDER=procedural|ai` override. Every
generated zone gets real tiling surface textures today; adding a key is a pure
upgrade.

### Web App — Browser Generate + Walk ✅

The browser UI is the primary way to use the tool today.

- **`server/app.py`** — FastAPI backend wrapping the generators. `POST /api/generate`
  builds a zone with a **fresh random seed** every call (identical inputs → different
  zone), serves the resulting `.glb` + `.zone.json` sidecar, and (when built) serves
  the front-end itself.
- **`web/`** — Vite + TypeScript single-page app. Three.js first-person viewer with
  WASD movement at EQ scale, pointer-lock mouse look, and toggleable light / region /
  wireframe overlays. Live metrics panel (seed, verts, polys, bounds).
- **`web/dev.mjs`** — single-command launcher: `npm run dev` spawns the Python backend,
  waits for its health check, then starts the bundler. One Ctrl+C stops both.

Verified end-to-end: a generate request from the browser reaches the backend through
the dev proxy, returns a random zone, and renders walkable in the viewport. Each click
of Generate produces a different seed and different geometry.

### Prompt-Driven Generation ✅

Type a description in the web UI and get a zone. Mirrors the texture system:
a no-API default with an LLM drop-in.

- **`RulePlanner`** (default) — keyword/heuristic parsing turns a prompt into a
  `ZonePlan`: detects theme (cave/outdoor/city/dungeon), size, verticality,
  explicit or implied room counts, and region kinds (water/lava/ice). "a big
  flooded cave with lots of chambers" → large cave, ~14 rooms, water region.
  No API, deterministic.
- **`LLMPlanner`** (optional) — OpenAI or Anthropic, selected by whichever key is
  present, using JSON-structured output grounded in the measured style profiles.
  Falls back to the rule planner on any failure.
- **`expand.plan_to_spec`** — turns the compact `ZonePlan` into a full `ZoneSpec`
  by driving the same `LayoutGenerator` the dropdowns use, so everything
  downstream (geometry, textures, packaging) is unchanged.

The web UI has a prompt box (Enter to generate) with the dropdowns tucked into a
"Controls" menu. The panel shows what the planner inferred (theme, size,
verticality, regions, mood) so you can see how it read your prompt.

```bash
# In the web UI:  "a towering multi-level temple with lava"
#   → dramatic verticality, lava region, dungeon theme
```

### Gating — Lock-and-Key Progression ✅

EQ has both open sprawls (Guk) and key-gated dungeons (Chardok). Gating is an
**optional** layer on top of the paced graph: ask for a keyed dungeon and the
layout gets locks on deep corridors with their keys placed earlier on the
critical path, so the zone is always **solvable**.

- **`GateSpec`** — serialisable gate record: the locked corridor, the lock
  position, the key room, the key position, and a difficulty tier. Carried on
  `ZoneSpec.gates` and round-tripped through the sidecar for the viewer and a
  future EQEmu door/key export.
- **`LayoutGenerator.generate(..., locks=N)`** — when `locks > 0`, `_apply_gating`
  runs a graph-rewrite-style placement: build the BFS tree from the entrance,
  lock the deepest tree edges first, then place each key in a room that is
  reachable **before** its lock and **not** behind a deeper lock. This preserves
  the solvability invariant — verified across dozens of randomly generated keyed
  dungeons in the test suite.
- **Planner integration** — the rule planner detects gating language ("keyed",
  "locked", "requires a key", explicit counts like "two locks") and sets a lock
  count; open-dungeon prompts stay open. The LLM planner can set it directly.
- **Viewer** — gates render as a red lock marker on the corridor, a gold key
  marker in its room, and a dashed line connecting them, toggleable in the
  Overlays panel. The panel shows the gate count.

```bash
# In the web UI:  "a keyed stone dungeon with two locked doors"
#   → 2 locks placed deep, keys reachable earlier, climax behind the last lock
```

## What's Next — Phase 4: Refinement

- Iterative chat loop: refine an existing zone with follow-up prompts
  ("make the entrance wider", "add a water pool to the north")
- Partial regeneration (re-run only changed rooms/textures)
- Server-side SQL export (zone records, spawn points) for EQEmu
- The room-graph grammar and water/mixed-zone work (see Roadmap Notes)

---

## File Format Notes

Targets **EQG Standard (v1–v3)**, the format used by the RoF2 client.

| File | Magic | Description |
|------|-------|-------------|
| `.eqg` | `PFS ` | PFS container archive (zlib-deflated chunks, `STEVE` footer) |
| `.ter` | `EQGT` | Zone terrain mesh: string table → materials → vertices → triangles |
| `.zon` | `EQGZ` | Zone placement: model list → object instances → regions → lights |
| `.dds` | `DDS ` | DirectX texture (DXT1 opaque / DXT5 alpha) |

TER vertex layout (v2): `float x,y,z` + `float nx,ny,nz` + `float u,v` = 32 bytes/vertex  
TER polygon: `uint32 v1,v2,v3` + `int32 material` + `uint32 flags` = 20 bytes/tri

Region name prefixes encode type: `AWT_`=water, `ALV_`=lava, `ATP_`=zoneline, `APK_`=PvP, `ASL_`=ice

Full format documentation: [`docs/file_formats.md`](docs/file_formats.md) _(to be written)_

---

## Reference Material

- [WLD File Reference by Windcatcher](https://vegaseq.com/docs/client/guides/file-formats/wld-by-windcatcher/) — legacy S3D format
- [EQEmu/zone-utilities](https://github.com/EQEmu/zone-utilities) — C++ structs and loaders (ground truth for EQG format)
- [xackery/quail](https://github.com/xackery/quail) — Go PFS implementation (archived Oct 2025)
- [EQGZI Getting Started](https://vegaseq.com/docs/client/eqgzi/getting-started-advanced/) — existing zone creation pipeline
- [knervous/eqsage](https://github.com/knervous/eqsage) — browser-based S3D/EQG viewer

---

## Geometric Fidelity by Era

To match EQ's look, generated geometry should sit at the same resolution the
original artists worked at — not smoother (reads as too modern) nor coarser.
The key metric is **median triangle edge length** (world units), measured from
real zones. The project reads both EQG (`.ter`) and now Classic–PoP (`.s3d`/WLD)
zones to establish this.

The hard format boundary is **Gates of Discord (2003)**: Classic → Planes of
Power ship as `.s3d`/WLD; GoD onward ship as `.eqg`.

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

The iconic **Classic/Kunark/PoP look clusters at ~12–14u median edge**, which is
the default target. The cave backend's default `voxel=12` produces ~12u edges —
a confirmed match for that era. Fidelity did not evolve monotonically; it
oscillated with art teams, tools, and zone type.

## Roadmap Notes / Future Work

Larger design directions captured for later (not yet implemented):

### Room-graph composition — TinyKeep + pacing + gating (done)

The "room-graph" is a zone's abstract floor-plan — rooms (nodes) connected by
corridors (edges) — that every geometry backend realises into 3D. The naive
random walk has been **replaced with a TinyKeep-style spatial layout** (see
`LayoutGenerator`):

1. Scatter rooms in an ellipse (sizes from a normal distribution → natural hubs)
2. Separate overlapping rooms (iterative push-apart; no physics engine)
3. Delaunay triangulation of room centres → candidate connection graph (scipy)
4. Minimum spanning tree → guarantees reachability, mostly tree-shaped
5. Add back ~12% of edges → loops / alternate paths so it's not purely linear
6. Assign elevation over the graph via BFS → connected rooms ramp/step between
7. Wall-to-wall corridors per edge

This fixes the old overlap/tangle/linearity problems and produces composed,
hub-and-branch layouts. All three geometry backends consume the result unchanged.

**Pacing (done).** On top of the spatial layout, the graph is analysed to give
each room a **role** and **graph depth**:
- *entrance* — a peripheral room (farthest from the layout centroid); the safe point
- *graph_depth* — BFS hops from the entrance; the progression axis
- *climax* — the deepest room (grand boss chamber)
- *hub* — a crossroads (graph degree ≥ 3)
- *deadend* — a leaf (reward/rare-spawn spot)

Geometry and lighting are biased by role & depth so the pacing is *visible*: the
climax is larger and taller, hubs are spacious, dead-ends intimate; interior
lighting fades and cools with depth (bright entrance → dim depths), and the
climax gets a charged/eerie tint. The sidecar carries the per-room pacing so the
viewer shows it and a future SQL/spawn export knows where the boss goes.

**Gating (done — optional lock-and-key).** EQ has both open sprawls (Guk) and
key-gated dungeons (Chardok). Gating layers onto the paced graph: locks go on
deep corridor edges, each key in a room reachable before its lock, climax behind
the final lock — placed by a graph-rewrite-style pass that guarantees
solvability. Carried as `GateSpec` data for the eventual EQEmu door/key export
and shown in the viewer. See the Gating section above.

**Still future:** Outdoor should turn its rooms into meaningful places
(clearings, lookouts) rather than only terrain bounds.

### Water and mixed-environment zones

Real EQ zones blend environments. Two cases to design for:
- **Outdoor areas adjacent to large bodies of water** — a lake/ocean edge means a
  water plane at a fixed Z, terrain that slopes beneath it to form a shoreline and
  lakebed, and an `AWT_` water region volume so the client treats it as swimmable.
  The terrain backend would need a "water level" and shoreline shaping.
- **Caves inside outdoor zones** — a cave mouth in a hillside: the SDF cave
  backend and the heightfield terrain backend would need to **compose into one
  TER**, carving the cave volume where it intersects the terrain and stitching the
  entrance. This is the strongest argument for eventually unifying both backends
  onto a single density-field representation (terrain as an SDF too), so a zone
  can be any mix of carved and surfaced geometry in one mesh.

---

## Known Issues / To Fix

- Style profiles for `city` and `cave` themes are thin (3–4 zones) — expand with more representatives once more zone names are identified.
- Light density stat reads 0 in the profile because most dungeon reference zones use embedded MOD placement without ZON lights — this is accurate, not a bug.
- The inspector's ASCII bbox diagram is proportional to zone size but doesn't render Z height — a future iteration could add a side-elevation view.
- Outdoor terrain is currently just the ground surface — no cliff walls, boulders, or vegetation yet, and rooms only set the terrain bounds (see room-graph note above).
- Procedural textures are diffuse-only. Real zones also use normal maps (the `e_TextureNormal0` material slot) for surface relief — adding procedural normal-map generation is a high-impact, no-API follow-up.

---

## Contributing

Contributions welcome. Open an issue before starting significant work.  
Run `python -m pytest tests/ -v` before submitting a PR — all tests must pass.

---

## License

MIT. EverQuest is a registered trademark of Daybreak Game Company LLC.  
This project is not affiliated with or endorsed by Daybreak Game Company LLC.  
No EverQuest game assets are included or distributed.
