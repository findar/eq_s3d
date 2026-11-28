# Engineering — plan

## Goal

The project stays fast to change and safe to run: tests that answer in minutes, builds that
reproduce, a local server that exposes nothing, agents that can work side by side without
clobbering each other, and docs a newcomer can follow.

## Scope

- Tests and their tiers (`tests/`, `pytest.ini`, `tests/conftest.py`), sweeps (`scripts/sweep_*.py`).
- Performance of builds and of the suite.
- Reproducibility, output confinement and server safety (`core/paths.py`, `server/app.py`).
- Agent workflow: worktrees, card-format specs, `scripts/task_status.py`, the single-writer
  tracker rule, commit trailers.
- Docs: this pillar tree, `docs/ARCHITECTURE.md`, `OPEN.md`, `ROADMAP.md`, steering.

## Non-goals

- Product features: every other pillar.

## Requirements

Umbrella cross-cutting requirements (they bind every pillar):

| ID | Requirement | Status now |
|---|---|---|
| ENG.26 | Determinism and fresh-seed randomness | Built: a pinned seed reproduces (footer aside); a fresh seed per generate. The in-process build-order leak was fixed in `6781622` |
| ENG.27 | Advisory data stays out of geometry and collision | Built (Property 5); pacing, gates, POIs in the sidecar |
| ENG.28 | No API required by default | Built: rule planner, rule edit interpreter, procedural textures |
| ENG.29 | Time budgets | Built: per-type timeouts, 8 attempts, 240 s budget; slow outdoor-dungeon Draws open (X-8) |
| ENG.30 | Local server security and session limits | Loopback bind, explicit CORS, segments checked with `fullmatch`; the session limits went with the Session store (decision 37) |
| ENG.31 | File-system confinement | Built: every write through `OutputRoot`; the EQ install is refused as an output |
| ENG.32 | Settled design constraints bind the system | Standing (each pillar's DECISIONS "Settled") |

Proposed new requirements (for the review):

| ID | Requirement (draft) | Status now |
|---|---|---|
| ENG.E1 | Test tiers: quick on every edit, full once at close, gate after geometry/layout/gate changes | Built (step 28) |
| ENG.E2 | Heavy runs (full, gate, sweeps) serialised across agents by a machine-wide lock | Planned (project-docs task 5, `scripts/heavy.py`) |
| ENG.E3 | Continuous integration, releases, and migration of saved builds across format changes | Not built (OPEN X-1) |
| ENG.E4 | A slice closes only when its pillar's DESIGN describes the new behaviour and its follow-ups are in OPEN | Planned (project-docs task 4) |
| ENG.E5 | A failure dashboard over `output/validation_failures.jsonl` and sweep results | Not built (OPEN X-2) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| M0 | [`zone-generator-m0-hygiene`](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) | done 2026-10-21 | 99 | Hypothesis property suite; cave pipeline and Flask viewer deleted; loopback bind and CORS; the gate made sound; agents re-pointed at spec `tasks.md` |
| 28 | [`test-speed`](../../../.kiro/specs/test-speed/tasks.md) | done 2026-11-25 | 15 | The suite in tiers; `gate` marker and `quick` profile; 3308 s → 1323 s full run |
| docs | [`project-docs`](../../../.kiro/specs/project-docs/tasks.md) | in progress | 1+ | Pillars, ARCHITECTURE, OPEN, one-page roadmap, tooling |

Also served by: M1 wave 6 (output confinement; P-B), step 12 (`scripts/stage.py`; P-H), and
the worktree tooling and card format, which landed as integration commits outside any slice.
