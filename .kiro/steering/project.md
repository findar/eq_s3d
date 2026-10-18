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

- **Commit regularly**, one logical change per commit. Remote is
  `github.com/findar/eq_s3d` (origin/master); push when work lands. Keep
  `README.md` and `ROADMAP.md` in sync when work lands.
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
- **Task tracking** lives in `tasks/` (tactical tier below ROADMAP). When you
  start work on something, open or create its `tasks/<id>.md` from
  `tasks/_TEMPLATE.md`; keep its `Status:` line, subtask checkboxes, and
  Deliverables (commit hashes) current as you go, and update the row in
  `tasks/README.md`. Set `Status: done` only when the acceptance criteria pass.
  Read the relevant task file before working — and VERIFY it against the actual
  code, because the repo can advance past the docs (it has before).
- **Running a task:** when the user points you at a `tasks/<id>.md` file (or
  names a task), treat that as an instruction to **run that task** — not merely
  to read or summarise it. That means: read the file, verify it against the
  current code (it can be stale), then work the unchecked subtasks toward the
  acceptance criteria, committing as you go and keeping the task file,
  `tasks/README.md`, and `ROADMAP.md` in sync. The task file's Goal /
  Acceptance criteria / Subtasks are the single source of truth for *what* to
  do; this always-on steering supplies the *how* (workflow, verification, the
  "structural tests pass ≠ done — eyeball it in 3D" rule). No per-task kickoff
  prompt is needed — pointing at the file is the trigger.

## Parallel agents (git worktrees)

Multiple agents can run at once, each in its **own git worktree on its own
branch**, so they never fight over the working directory. Worktrees share one
`.git`; conflict avoidance comes from branch-per-agent + module partitioning +
merging often, NOT from worktrees alone.

- **Create a worktree with the helper, never by hand:**
  `./scripts/new-worktree.ps1 -Branch agent/<scope>`. It lands a ready checkout
  at `..\eq_s3d-worktrees\<scope>` (sibling of the repo, forked from `master`)
  and bootstraps the gitignored files a fresh worktree lacks.
- **If you were spawned into a worktree, STAY in it.** Work only your branch,
  commit there, push it (`git push -u origin <branch>`). Never
  `git checkout`/`switch` to another branch inside a worktree, never run two
  agents in the same directory, and don't rebase/merge another agent's in-flight
  branch unless told to.
- **Partition by module** using the repo map above — `core/`,
  `generators/field/`, `generators/textures/`, `ai/`, `server/`, `web/` are the
  natural seams. Agents in different directories rarely collide.
- **Shared-state conflict hotspots** across branches: `ROADMAP.md`,
  `tasks/README.md`, `generators/pipeline.py`, `main.py`, `requirements.txt`.
  Keep edits to these minimal, merge frequently, and prefer touching only your
  own `tasks/<id>.md`. Expect to hand-resolve these at merge time.
- **Gitignored state is not shared into a fresh worktree** — the script handles
  it: copies `.env`, junctions `web/node_modules` from the main worktree
  (shared, so don't mutate web deps there — use `-IsolateNode` if your task
  changes `web/package.json`), and shares the global Python env unless you pass
  `-Venv`. If your task edits `requirements.txt`, recreate the worktree with
  `-Venv` so you don't change everyone's environment.
- **`output/` is per-worktree by design** — generate freely; your `.eqg`/`.glb`/
  `.png` artifacts won't clobber another agent's.
- **Tear down from the MAIN checkout** once a branch is merged:
  `git worktree remove "..\eq_s3d-worktrees\<scope>"` (clears the junction
  cleanly), then delete the branch.
- **Keep `scripts/new-worktree.ps1` committed on `master`** — a worktree forked
  from `master` only inherits the tooling if it's tracked there.
