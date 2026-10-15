# eq_s3d — Agentic EverQuest Zone Generator

Generate EverQuest EQG zone files from natural language prompts, targeting the **RoF2 client**.

> **Status**: Organic caves with walkable floors + natural features ✅ — stalactites, stalagmites, pillars. Phase 3 (AI integration) up next

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
core/       — Binary I/O: PFS container, TER terrain, ZON placement
analyzer/   — Extract style metrics from existing EQ zones
  ├─ extractor.py   — per-zone metric extraction
  ├─ style_builder.py — build style profile JSONs from a corpus
  └─ inspect.py     — rich terminal inspector + zone comparator
generators/ — Procedural geometry, lighting, region volumes
  ├─ zone_spec.py   — serialisable ZoneSpec (the IR)
  ├─ geometry.py    — MeshBuilder: box rooms, corridors, ramps, stairs
  ├─ layout.py      — LayoutGenerator: seedable 3D room-graph
  ├─ textures.py    — placeholder DDS (AI textures in Phase 3)
  ├─ field/         — organic (SDF + marching cubes) geometry
  │   ├─ sdf.py      — density-field primitives (sphere/capsule/cone/dome) + carve
  │   ├─ noise.py    — fast vectorised FBM value noise (wall roughness)
  │   ├─ cave.py     — carve chambers+tunnels, walkable flat floors
  │   ├─ features.py — stalactites / stalagmites / pillars (surface-aware)
  │   └─ mesh.py     — marching cubes → TerFile + decimation
  └─ builder.py     — ZoneBuilder: routes box vs organic backend → .eqg + .glb
server/     — FastAPI backend wrapping the generators for the web UI
web/        — Vite + TypeScript browser app (Three.js first-person viewer)
viewer/     — Legacy standalone Flask GLB preview (superseded by web/)
ai/         — LLM planner, texture generation, iterative agent   [Phase 3]
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
| **3** | AI integration — LLM planner, prompt → ZoneSpec, texture gen | 🔨 Next |
| **4** | Refinement — partial regen, style learning, SQL export | ⏳ |

---

## What's Done

### Phase 0 — Zone Analyzer ✅

Reads any `.eqg` archive from a RoF2 install and extracts measurable style metrics:
bounding dimensions, polygon density, material counts, shader usage, light density,
and region type distribution.

Style profiles derived from real RoF2 zones (stored in `styles/`):

| Theme | Zones | Ceiling range | Materials (mean) | Key shaders |
|-------|-------|--------------|-----------------|-------------|
| `dungeon` | 10 | 77–10,560 u | 51 | `Opaque_MPLBump2UV`, `Opaque_MPLBump` |
| `outdoor` | 6 | 449–1,494 u | varies | `Opaque_MaxLava`, `Opaque_MaxCB1` |
| `city` | 3 | 157–3,132 u | 71 | `Opaque_MaxWater`, `Opaque_MPLBump` |
| `cave` | 4 | 133–4,067 u | 41 | `Opaque_MPLBump2UV`, `Opaque_MPLGB` |

These profiles constrain the AI generator so output stays within the measured bounds
of real EQ zones.

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

## What's Next — Phase 3: AI Integration

- `ai/planner.py` — LLM prompt → `ZoneSpec` JSON (structured output / tool use)
- `ai/style.py` — load style profiles as generation constraints
- `generators/textures.py` — replace placeholders with real AI-generated DDS textures
- `ai/agent.py` — iterative chat loop: refine zones with follow-up prompts
- add a prompt box to the web UI, posting to `/api/generate`'s `prompt` field

Target: type a natural-language prompt, get a styled, textured, walkable zone, then
refine it conversationally — all in the browser UI that already exists.

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

## Known Issues / To Fix

- Style profiles for `city` and `cave` themes are thin (3–4 zones) — expand with more representatives once more zone names are identified.
- Light density stat reads 0 in the profile because most dungeon reference zones use embedded MOD placement without ZON lights — this is accurate, not a bug.
- The inspector's ASCII bbox diagram is proportional to zone size but doesn't render Z height — a future iteration could add a side-elevation view.

---

## Contributing

Contributions welcome. Open an issue before starting significant work.  
Run `python -m pytest tests/ -v` before submitting a PR — all tests must pass.

---

## License

MIT. EverQuest is a registered trademark of Daybreak Game Company LLC.  
This project is not affiliated with or endorsed by Daybreak Game Company LLC.  
No EverQuest game assets are included or distributed.
