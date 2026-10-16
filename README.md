# eq_s3d — EverQuest Zone Generator

Generate EverQuest zone files from natural-language prompts, targeting the
**RoF2 client**, and walk through the result in your browser — no 3D modelling
required. The tool handles geometry, textures, lighting, and packaging, and
produces a `.eqg` for the client plus a `.glb` preview.

The output is meant as a **starting point for a manual authoring pass**, not a
finished zone: layouts, pacing, and lock/key placement are generated as
suggestions you can accept, move, or ignore.

> **Project status and roadmap:** see **[`ROADMAP.md`](ROADMAP.md)**.

---

## Features

- **Prompt-driven generation** — describe a zone ("a big flooded cave with lots
  of chambers") and get a playable layout. Works with no API key via a built-in
  rule planner; an LLM planner is an optional drop-in.
- **Natural, era-accurate geometry** — organic caves (SDF + marching cubes),
  eroded outdoor terrain, and box dungeons/cities, sized and detailed to match
  the Classic–Planes-of-Power look.
- **Walk it in the browser** — a first-person Three.js viewer with WASD movement
  at EQ scale, a top-down map, and toggleable light/region/gate overlays.
- **Composed layouts** — a TinyKeep-style room graph with pacing (entrance / hub
  / climax / dead-end) and optional, solvability-guaranteed lock-and-key gating.
- **Theme-conforming rooms (dungeon)** — a content layer gives each room a
  semantic type drawn from a zone archetype (fortress, temple, tomb,
  wizard-lair, sunken ruin, forge, ice keep, …), scaled by an inhabiting race
  (giant halls dwarf a froglok warren) with optional lava/ice/water tint. Shape,
  region volumes, lighting mood, and palette are realised into geometry; props,
  encounters, and boss placement are carried as written suggestions (no new
  art, no placed props).
- **No-API by default** — procedural textures and the rule planner need no keys;
  AI texture generation and the LLM planner activate only when a key is present.
- **Random by default** — every generation uses a fresh seed, so identical
  inputs still produce a different zone (pin a seed to reproduce one).

## How it works

```
Prompt → Planner → ZoneSpec → ┬─ Geometry (TER)
                              ├─ Textures (DDS)
                              └─ Lights / Regions (ZON)
                                        │
                              PFS packer → .eqg  +  .glb (browser preview)
```

The **ZoneSpec** is a serialisable JSON intermediate; a geometry backend (box,
organic cave, or heightfield terrain) is chosen by theme. See `ROADMAP.md` for
the design detail behind each stage.

---

## Setup

```bash
git clone https://github.com/findar/eq_s3d.git
cd eq_s3d

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set EQ_PATH to your RoF2 install, and any AI/LLM API keys (optional)
```

**Requirements:** Python 3.11+, and a legally-obtained RoF2 client install (used
only for style analysis — no game assets are distributed).

---

## Usage

### Web app — generate and walk zones (recommended)

One command starts everything (it spawns the Python backend, waits for it to be
healthy, then starts the front-end bundler; one Ctrl+C stops both):

```bash
cd web && npm install   # first time only
npm run dev
#    → open http://localhost:5173
```

Type a description and hit **Generate** (or use the dropdowns under *Controls*
for theme / room count / elevation). Click the viewport to capture the mouse,
then walk with **WASD** (Shift sprint, Q/E down/up, R reset). Press **M** for a
top-down map. Toggle wireframe / light / region / gate overlays in the side
panel.

Production build (served entirely by the Python backend, no Node needed to run):

```bash
cd web && npm run build
python -m uvicorn server.app:app --port 8000
#    → open http://localhost:8000
```

### Command line

```bash
python main.py generate myrealm --theme dungeon --rooms 5 --seed 42
```

Output lands in `output/`: `myrealm.eqg` (for the client), `myrealm.glb`
(browser preview), `myrealm.zone.json` (lights/regions/pacing sidecar), and
`myrealm.json` (the editable ZoneSpec).

### Inspect a zone against the style profile

```bash
# Single zone, compared to its theme's measured style profile
python -m analyzer.inspect F:/everquest_rof2/bertoxtemple.eqg --theme dungeon

# Two zones side by side
python -m analyzer.inspect zone_a.eqg --compare zone_b.eqg
```

### Rebuild style profiles from your EQ install (optional, one-time)

```bash
python -m analyzer.style_builder --eq-path "F:/everquest_rof2" --all
```

Reads reference zones and writes empirical style profiles to `styles/`.
Pre-built RoF2 profiles are already included in the repo.

### Run the tests

```bash
python -m pytest tests/ -q
```

---

## Project layout

```
core/       Binary I/O: PFS container, TER terrain, ZON placement, WLD reader
analyzer/   Extract style metrics from existing EQ zones; terminal inspector
generators/ ZoneSpec (IR), geometry backends, layout, textures, top-down map
  field/      Organic cave (SDF + marching cubes) and heightfield terrain
  textures/   Procedural (default) and AI texture providers
ai/         Prompt → ZonePlan → ZoneSpec (rule planner default, LLM drop-in)
server/     FastAPI backend wrapping the generators for the web UI
web/        Vite + TypeScript browser app (Three.js first-person viewer)
styles/     Empirically-derived style profiles per theme
tests/      pytest suite
```

---

## File format reference

Targets **EQG Standard (v1–v3)**, the format used by the RoF2 client.

| File | Magic | Description |
|------|-------|-------------|
| `.eqg` | `PFS ` | PFS container archive (zlib-deflated chunks, `STEVE` footer) |
| `.ter` | `EQGT` | Zone terrain mesh: string table → materials → vertices → triangles |
| `.zon` | `EQGZ` | Zone placement: model list → object instances → regions → lights |
| `.dds` | `DDS ` | DirectX texture (DXT1 opaque / DXT5 alpha) |

- TER vertex (v2): `float x,y,z` + `float nx,ny,nz` + `float u,v` = 32 bytes
- TER polygon: `uint32 v1,v2,v3` + `int32 material` + `uint32 flags` = 20 bytes
- Region name prefixes encode type: `AWT_`=water, `ALV_`=lava, `ATP_`=zoneline,
  `APK_`=PvP, `ASL_`=ice
- EverQuest is **Z-up**; collision is per-triangle (no BSP tree).

---

## Reference material

- [WLD File Reference by Windcatcher](https://vegaseq.com/docs/client/guides/file-formats/wld-by-windcatcher/) — legacy S3D format
- [EQEmu/zone-utilities](https://github.com/EQEmu/zone-utilities) — C++ structs and loaders (ground truth for EQG format)
- [xackery/quail](https://github.com/xackery/quail) — Go PFS implementation (archived Oct 2025)
- [EQGZI Getting Started](https://vegaseq.com/docs/client/eqgzi/getting-started-advanced/) — existing zone creation pipeline
- [knervous/eqsage](https://github.com/knervous/eqsage) — browser-based S3D/EQG viewer

For the procedural-generation approaches we investigated and why we chose what we
chose (TinyKeep, BSP/WFC/CA, Dormans graph rewriting, Labyrinth, SDF caves), see
[`docs/RESEARCH.md`](docs/RESEARCH.md).

---

## Contributing

Contributions welcome. Open an issue before starting significant work, and run
`python -m pytest tests/ -q` before submitting a PR — all tests must pass. See
[`ROADMAP.md`](ROADMAP.md) for what's in flight and what's open.

---

## License

MIT. EverQuest is a registered trademark of Daybreak Game Company LLC. This
project is not affiliated with or endorsed by Daybreak Game Company LLC. No
EverQuest game assets are included or distributed.
