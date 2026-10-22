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
  `mapview.py` (top-down SVG), `field/` (heightfield terrain + value noise),
  `textures/` (procedural + AI)
- `ai/` — `schema.py`, `rule_planner.py`, `llm_planner.py`, `expand.py`, `planner.py`
- `server/` — FastAPI backend (`app.py`)
- `web/` — Vite + TS Three.js app (`src/{main,scene,controls,api}.ts`)
- `styles/` — measured per-theme style profiles (JSON)
- `tests/` — pytest

## Architecture conventions

- The **ZoneSpec** (`generators/zone_spec.py`) is the IR everything flows
  through: planner → ZoneSpec → geometry/textures/placement → `.eqg` + `.glb`.
- Geometry backends are selected by theme in `builder.py`: box (dungeon/city)
  and heightfield terrain (outdoor). All consume the same
  layout output unchanged — keep it that way.
- **Z is up** (EverQuest convention). Three.js defaults to Y-up; the web camera
  is configured for Z-up on purpose.
- Advisory data (pacing roles, gates) rides in the `.zone.json` sidecar, never
  in the binary.

## Workflow expectations

- **Commit regularly**, one logical change per commit, and **push `master`
  periodically** (`git push origin master`) so local commits don't pile up
  unpushed. The remote (`github.com/findar/eq_s3d`) is purely BACKUP for a
  single-machine setup, so keeping `master` current there is the whole point —
  push after commits, not just once at the very end. **Don't push agent
  branches:** they're local-only, short-lived, and merged into `master` from the
  MAIN checkout (which is what gets pushed). Pushing branches adds no value on
  one machine.
- **Tracker ownership is single-writer — one unconditional rule, solo or
  parallel.** While working a task you update ONLY that task's own entry — its
  `.kiro/specs/<feature>/tasks.md` for new work (or a legacy `tasks/<id>.md` for
  historical work): Status/checkbox state, subtask checkboxes, Deliverables /
  commit hashes. You do NOT edit `ROADMAP.md`, `README.md`, or `tasks/README.md`
  as part of task work. Those three are *integration state*, written once per landed branch
  by a single explicit integration step run from the MAIN checkout. This is
  unconditional ON PURPOSE: a working agent usually cannot tell whether other
  agents are running right now, so a rule that only applied "when parallel" would
  eventually guess wrong and clobber `ROADMAP.md` at merge time. One rule erases
  that whole class of conflict. When you finish, surface a short **integration
  note** — the Done-table row, "Pick up here" line, commit hash/count, and the
  `tasks/README.md` status change — so whoever integrates applies it in that one
  serialized step.
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
  a human looking at the result can confirm. The `ROADMAP.md` "Pick up here" +
  Done table and commit count/hash go in the integration note, not written by
  you directly (see tracker ownership above).
- **Task tracking** for NEW work lives in `.kiro/specs/<feature>/tasks.md` — the
  spec task list is the unit of work. When you start work on something, open or
  create its entry in that spec's `tasks.md`; keep its `Status:`/checkbox state,
  subtask checkboxes, and Deliverables (commit hashes) current as you go. (The
  `tasks/README.md` index row is integration state — updated in the single-writer
  integration step, not here; see tracker ownership.) Mark a task done only when
  its acceptance criteria pass. Read the relevant spec `tasks.md` entry (and the
  spec's `requirements.md`/`design.md`) before working — and VERIFY it against the
  actual code, because the repo can advance past the docs (it has before).
  The legacy `tasks/<id>.md` tactical tier is kept as **history**: prior work
  lives there for reference, but new work goes in the spec `tasks.md`.
- **Running a task:** when the user points you at a spec `tasks.md` task (or a
  legacy `tasks/<id>.md` file, or names a task), treat that as an instruction to
  **run that task** — not merely to read or summarise it. That means: read the
  task, verify it against the current code (it can be stale), then work the
  unchecked subtasks toward the acceptance criteria, committing as you go and
  keeping the task entry in sync. (`tasks/README.md` and `ROADMAP.md` are updated
  only in the single-writer integration step — see tracker ownership.) The task's
  Goal / Acceptance criteria / Subtasks are the single source of truth for *what*
  to do; this always-on steering supplies the *how* (workflow, verification, the
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
- **If you were spawned into a worktree, STAY in it.** Work only your branch and
  commit there — do NOT push the branch (it's local-only and gets merged into
  `master` from the MAIN checkout, which is what's pushed for backup). Never
  `git checkout`/`switch` to another branch inside a worktree, never run two
  agents in the same directory, and don't rebase/merge another agent's in-flight
  branch unless told to.
- **Partition by module** using the repo map above — `core/`,
  `generators/field/`, `generators/textures/`, `ai/`, `server/`, `web/` are the
  natural seams. Agents in different directories rarely collide.
- **Tracker files are already handled** by the single-writer rule above —
  `ROADMAP.md`, `README.md`, and `tasks/README.md` are never written during task
  work, so they can't conflict across branches. The remaining cross-branch
  hotspots are CODE: `generators/pipeline.py`, `main.py`, `requirements.txt`.
  Single-writer isn't an option for code, so partition the work such that only
  one agent owns each of these at a time, keep edits minimal, and merge often.
- **Gitignored state is not shared into a fresh worktree** — the script handles
  it: copies `.env`, junctions `web/node_modules` from the main worktree
  (shared, so don't mutate web deps there — use `-IsolateNode` if your task
  changes `web/package.json`), and shares the global Python env unless you pass
  `-Venv`. If your task edits `requirements.txt`, recreate the worktree with
  `-Venv` so you don't change everyone's environment.
- **`output/` is per-worktree by design** — generate freely; your `.eqg`/`.glb`/
  `.png` artifacts won't clobber another agent's.
- **Tear down from the MAIN checkout** once a branch is merged, using
  `./scripts/remove-worktree.ps1 -Branch <scope> -DeleteBranch`. **Never** use a
  bare `git worktree remove` here: on Windows it follows the shared
  `web/node_modules` junction and deletes files inside the MAIN repo's
  `node_modules` (verified — it will gut the primary checkout). The remove script
  unlinks the junction first, then removes the worktree safely.
- **Keep `scripts/new-worktree.ps1` committed on `master`** — a worktree forked
  from `master` only inherits the tooling if it's tracked there.
