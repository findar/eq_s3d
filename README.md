# eq_s3d — Agentic EverQuest Zone Generator

Generate EverQuest EQG zone files from natural language prompts, targeting the RoF2 client.

> **Status**: Phase 1 — Core I/O (in progress)

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

---

## Architecture

```
core/       — Binary I/O: PFS container, TER terrain, ZON placement
analyzer/   — Extract style metrics from existing EQ zones
generators/ — Procedural geometry, lighting, region volumes
ai/         — LLM planner, texture generation, iterative agent
viewer/     — Browser-based Three.js preview (GLB + Flask)
styles/     — Empirically-derived style profiles per zone theme
```

**Pipeline**:
```
User Prompt → AI Planner → ZoneSpec JSON
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
          Geometry        Textures         Lights/Regions
          (TER file)      (DDS files)      (ZON file)
                └──────────────┼──────────────┘
                               ▼
                        PFS → .eqg + .glb
```

---

## Setup

```bash
git clone https://github.com/yourname/eq_s3d.git
cd eq_s3d
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set EQ_PATH and your AI API keys
```

---

## Phase 1: Validate Core I/O

Before generating anything, verify the binary writers work against your EQ install:

```bash
# Run the test suite
python -m pytest tests/ -v

# Analyze a zone from your EQ install (builds style profiles)
python -m analyzer.style_builder --eq-path "C:/EverQuest" --theme dungeon

# View a style profile
cat styles/dungeon.json
```

---

## Project Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Zone analyzer — extract style profiles from EQ install | 🔨 |
| 1 | Core I/O — PFS, TER, ZON binary writers | 🔨 |
| 2 | Procedural geometry — box rooms, corridors, lighting | ⏳ |
| 3 | AI integration — LLM planner, texture generation | ⏳ |
| 4 | Refinement — partial regen, style learning | ⏳ |

---

## File Format Notes

Targets **EQG Standard (v1–v3)**, the format used by the RoF2 client:

- **PFS** — custom zlib container (`PFS ` magic, `STEVE` footer)
- **TER** — zone terrain mesh (`EQGT` magic): string table + materials + vertices + triangles
- **ZON** — placement data (`EQGZ` magic): model list + object instances + regions + lights
- **DDS** — DirectX texture format (DXT1 opaque / DXT5 alpha)

Full format documentation: [`docs/file_formats.md`](docs/file_formats.md)

---

## Reference Material

- [WLD File Reference by Windcatcher](https://vegaseq.com/docs/client/guides/file-formats/wld-by-windcatcher/)
- [EQEmu/zone-utilities](https://github.com/EQEmu/zone-utilities) — C++ source with struct definitions
- [xackery/quail](https://github.com/xackery/quail) — Go PFS implementation (archived)
- [EQGZI Getting Started](https://vegaseq.com/docs/client/eqgzi/getting-started-advanced/)

---

## License

MIT. EverQuest is a registered trademark of Daybreak Game Company LLC.  
This project is not affiliated with or endorsed by Daybreak Game Company LLC.  
No EverQuest game assets are included or distributed.
