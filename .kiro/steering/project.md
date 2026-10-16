# eq_s3d — project guidance for the agent

Always-on context for working in this repo. Read `ROADMAP.md` for the open-items
tracker and `lessons-learned.md` (also steering) for hard-won technical gotchas.

## What this is

A Python tool that procedurally generates EverQuest zone resources for the
**RoF2 client**, driven by natural-language prompts, viewable in a browser. The
output is a starting point for a human authoring pass, not a finished zone.

## North-star intent (from the user, don't drift from these)

- **Indistinguishable from a hand-crafted zone.** Favour *natural* geometry
  (caves, hills, earthen walls, pillars, stalactites) over clean architecture.
- **Classic–PoP era is the default look.** That era ships as `.s3d`/WLD; GoD+
  ships as `.eqg`. We read both for analysis; we currently *write* EQG.
- **Navigable.** Floors must be walkable — gentle undulation is fine, pits and
  slippery bowls are not. Verified by walkability tests; don't regress them.
- **No manual modelling.** Everything is prompt-driven / parameter-driven.
- **No API required by default.** Procedural textures and the rule planner work
  with zero keys; AI (textures) and LLM (planner) are optional drop-ins.
- **Randomness is a feature.** Same inputs should not give the same output
  (fresh seed per generate unless pinned).
- **Generation under ~5 minutes is acceptable** — relaxes the voxel budget, but
  keep the interactive web loop snappy where you can.
- **Layouts are suggestions.** Pacing/gating are advisory metadata for a manual
  finishing pass; they must not alter geometry or collision.

## Repo map

- `core/` — binary I/O: `pfs.py`, `ter.py`, `zon.py`, `eqg.py`, `wld.py`
- `analyzer/` — extract style metrics; `inspect.py`, `style_builder.py`
- `generators/` — `zone_spec.py` (the IR), `geometry.py` (box backend),
  `layout.py` (TinyKeep + pacing + gating), `builder.py` (orchestrator),
  `mapview.py` (top-down SVG), `field/` (SDF cave + terrain + noise + mesh),
  `textures/` (procedural + AI)
- `ai/` — `schema.py`, `rule_planner.py`, `llm_planner.py`, `expand.py`, `planner.py`
- `server/` — FastAPI backend (`app.py`)
- `web/` — Vite + TS Three.js app (`src/{main,scene,controls,api}.ts`)
- `styles/` — measured per-theme style profiles (JSON)
- `tests/` — pytest

## Architecture conventions

- The **ZoneSpec** (`generators/zone_spec.py`) is the IR everything flows
  through: planner → ZoneSpec → geometry/textures/placement → `.eqg` + `.glb`.
- Geometry backends are selected by theme in `builder.py`: box (dungeon/city),
  organic cave (cave), heightfield terrain (outdoor). All consume the same
  layout output unchanged — keep it that way.
- **Z is up** (EverQuest convention). Three.js defaults to Y-up; the web camera
  is configured for Z-up on purpose.
- Advisory data (pacing roles, gates) rides in the `.zone.json` sidecar, never
  in the binary.

## Workflow expectations

- **Commit regularly**, one logical change per commit. Local git only (no remote
  configured yet). Keep `README.md` and `ROADMAP.md` in sync when work lands.
- **Run the suite before claiming done**: `python -m pytest tests/ -q`. Build the
  frontend when web files change: `cd web && npx vite build`.
- **Don't add tests unless they're warranted** by the change (regressions, new
  features). The user doesn't want test-for-test's-sake.
- Prefer fixing a root cause over loosening a test. When a walkability or
  solvability test fails, that's usually a real geometry/graph bug.
- Analytical/test verification is good, but note when something was NOT verified
  in the live 3D viewer so the user knows to eyeball it.
- After a **major change** (geometry backend, layout, pacing/gating, textures,
  viewer), walk `docs/ACCEPTANCE.md` — the manual UAT checklist for things only
  a human looking at the result can confirm. Update `ROADMAP.md` ("Pick up here"
  + Done table) and the commit count/hash when work lands.
