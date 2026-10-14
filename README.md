# eq_s3d — Agentic EverQuest Zone Generator

Generate EverQuest EQG zone files from natural language prompts, targeting the **RoF2 client**.

> **Status**: Phase 1 complete ✅ — Phase 2 (procedural geometry) up next

---

## What It Does

Type a prompt, get a playable `.eqg` zone file and a browser preview:

```
> generate a dark stone dungeon with a lava river and torch lighting
→ output/myrealm.eqg    (drop into your EQ directory)
→ output/myrealm.glb    (opens in browser for preview)
```

Iterate with follow-up prompts:

```
> make the entrance corridor wider
> add a second room to the north with a water pool
> the lava texture needs to look more molten
```

No 3D modelling required at any step. The tool handles geometry, textures, lighting, and packaging.

---

## Architecture

```
core/       — Binary I/O: PFS container, TER terrain, ZON placement
analyzer/   — Extract style metrics from existing EQ zones
generators/ — Procedural geometry, lighting, region volumes      [Phase 2]
ai/         — LLM planner, texture generation, iterative agent   [Phase 3]
viewer/     — Browser-based Three.js preview (GLB + Flask)
styles/     — Empirically-derived style profiles per zone theme  ✅
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

### Build style profiles from your EQ install (do this once)

```bash
python -m analyzer.style_builder --eq-path "F:/everquest_rof2" --all
```

This reads geometry data from reference zones and writes empirical style profiles
to `styles/`. Pre-built profiles for RoF2 are included in this repo.

### Run the test suite

```bash
python -m pytest tests/ -v
# 31 passed
```

---

## Project Phases

| Phase | Description | Status |
|-------|-------------|--------|
| **0** | Zone analyzer — extract style profiles from RoF2 install | ✅ Done |
| **1** | Core I/O — PFS reader/writer, TER/ZON binary serialisers | ✅ Done |
| **2** | Procedural geometry — rooms, corridors, lighting, regions | 🔨 Next |
| **3** | AI integration — LLM planner, prompt → ZoneSpec, texture gen | ⏳ |
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

---

## What's Next — Phase 2: Procedural Geometry

Build the zone geometry generator that converts a `ZoneSpec` (structured JSON describing
rooms, corridors, and features) into TER/ZON binary files:

- `generators/geometry.py` — box rooms, corridors, arched ceilings, stairs
- `generators/layout.py` — room connectivity graph, door placement, zone bounds
- `generators/lighting.py` — torch/ambient light placement heuristics
- `generators/regions.py` — water/lava/zoneline region volume helpers

Target: flat-shaded box zones with placeholder textures that load correctly in the
RoF2 client and are walkable. This validates the full write path end-to-end.

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

- UV scale statistics in style profiles are skewed by extreme float values in some zone TER files — needs outlier clipping before Phase 3.
- Light count reads as 0 for all RoF2 zones — lights may be stored in a different file or format than the classic ZON structure. Needs investigation.
- Style profiles for `city` theme are from only 3 zones — expand once more city zones are identified.

---

## Contributing

Contributions welcome. Open an issue before starting significant work.  
Run `python -m pytest tests/ -v` before submitting a PR — all tests must pass.

---

## License

MIT. EverQuest is a registered trademark of Daybreak Game Company LLC.  
This project is not affiliated with or endorsed by Daybreak Game Company LLC.  
No EverQuest game assets are included or distributed.
