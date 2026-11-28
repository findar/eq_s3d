# P-9 Engineering — plan

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

## Goal

The project stays fast to change and safe to run: tests that answer in minutes, builds that
reproduce, a local server that exposes nothing, agents that can work side by side without
clobbering each other, and docs a newcomer can follow.

## Scope

- Tests and their tiers ([`tests/`](../../../tests), [`pytest.ini`](../../../pytest.ini), [`tests/conftest.py`](../../../tests/conftest.py)), sweeps (`scripts/sweep_*.py`).
- Performance of builds and of the suite.
- Reproducibility, output confinement and server safety ([`core/paths.py`](../../../core/paths.py), [`server/app.py`](../../../server/app.py)).
- Agent workflow: worktrees, card-format specs, [`scripts/task_status.py`](../../../scripts/task_status.py), the single-writer
  tracker rule, commit trailers.
- Docs: this pillar tree, [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md), [`OPEN.md`](../../../OPEN.md), [`ROADMAP.md`](../../../ROADMAP.md), and the always-on steering in [`.kiro/steering/`](../../../.kiro/steering).

## Non-goals

- Product features: every other pillar.

## Requirements

The umbrella's cross-cutting requirements (they bind every pillar), then drafts with proposed
parents, listed in the [pillar README](../README.md#proposed-product-requirements).

| ID | Requirement | Parent | Status now |
|---|---|---|---|
| <a id="p-9-req-1"></a>P-9-Req-1 | A pinned seed reproduces its build; otherwise each generate gets a fresh seed | [ZG-Req-26](../../../.kiro/specs/zone-generator/requirements.md#requirement-26-determinism-and-fresh-seed-randomness) | Built: a pinned seed reproduces (apart from the archive footer's timestamp). A zone used to build differently after another zone in the same process; `6781622` fixed it |
| <a id="p-9-req-2"></a>P-9-Req-2 | Advisory data stays out of geometry and collision | [ZG-Req-27](../../../.kiro/specs/zone-generator/requirements.md#requirement-27-advisory-data-stays-out-of-geometry-and-collision) | Built ([Property 5](../../../.kiro/specs/zone-generator/design.md#property-5-advisory-isolation)): pacing, Gates and POIs ride in the sidecar |
| <a id="p-9-req-3"></a>P-9-Req-3 | No API is required by default | [ZG-Req-28](../../../.kiro/specs/zone-generator/requirements.md#requirement-28-no-api-required-by-default) | Built: the rule planner, the rule edit interpreter, procedural textures |
| <a id="p-9-req-4"></a>P-9-Req-4 | Time budgets | [ZG-Req-29](../../../.kiro/specs/zone-generator/requirements.md#requirement-29-time-budgets) | Built: timeouts per zone type, 8 attempts, a 240 s budget. Slow outdoor-dungeon Draws stay open ([P-9-8](OPEN.md#p-9-8)) |
| <a id="p-9-req-5"></a>P-9-Req-5 | The local server exposes nothing beyond this machine | [ZG-Req-30](../../../.kiro/specs/zone-generator/requirements.md#requirement-30-local-server-security-and-session-limits) | Built: it binds to loopback only, with an explicit CORS list (which web origins may call it), and checks path segments with `fullmatch`. The session limits went with the Session store ([umbrella decision 37](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)) |
| <a id="p-9-req-6"></a>P-9-Req-6 | Writes stay inside the output folder | [ZG-Req-31](../../../.kiro/specs/zone-generator/requirements.md#requirement-31-file-system-confinement) | Built: every write goes through `OutputRoot`; the EQ install is refused as an output |
| <a id="p-9-req-7"></a>P-9-Req-7 | The settled design constraints bind the system | [ZG-Req-32](../../../.kiro/specs/zone-generator/requirements.md#requirement-32-settled-design-constraints) | Standing: each pillar's `DECISIONS.md` "Settled" list |
| <a id="p-9-req-8"></a>P-9-Req-8 | Test tiers: quick on every edit, full once at a task's close, gate after geometry, layout or gate changes | proposed: [ZG-Req-38](../README.md#zg-req-38) | Built ([step 28](../../../.kiro/specs/test-speed/tasks.md)) |
| <a id="p-9-req-9"></a>P-9-Req-9 | Heavy runs (full, gate, sweeps) are serialised across agents by a lock for the whole machine | proposed: [ZG-Req-39](../README.md#zg-req-39) | Planned ([project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md), `scripts/heavy.py`) ([P-9-3](OPEN.md#p-9-3)) |
| <a id="p-9-req-10"></a>P-9-Req-10 | Continuous integration, releases, and migration of saved builds across format changes | proposed: [ZG-Req-40](../README.md#zg-req-40) | Not built ([P-9-1](OPEN.md#p-9-1)) |
| <a id="p-9-req-11"></a>P-9-Req-11 | A slice closes only when its pillar's `DESIGN.md` describes the new behaviour and its follow-ups are in its `OPEN.md` | proposed: [ZG-Req-41](../README.md#zg-req-41) | Planned ([project-docs task 4](../../../.kiro/specs/project-docs/cards/04-roadmap.md)) |
| <a id="p-9-req-12"></a>P-9-Req-12 | A failure dashboard over `output/validation_failures.jsonl` and sweep results | proposed: [ZG-Req-42](../README.md#zg-req-42) | Not built ([P-9-2](OPEN.md#p-9-2)) |

## Traceability

Which slices served each requirement. ([`scripts/task_status.py`](../../../scripts/task_status.py)
will generate this table after [project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md).)

| Requirement | Served by |
|---|---|
| [P-9-Req-1](#p-9-req-1) | [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) (properties), [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) (stage seeds), [step 32](../../../.kiro/specs/zone-generator-races-followups/tasks.md) (the build-order fix) |
| [P-9-Req-2](#p-9-req-2) | [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) ([Property 5](../../../.kiro/specs/zone-generator/design.md#property-5-advisory-isolation)) |
| [P-9-Req-3](#p-9-req-3) | pre-spec Phase 3, [step 18](../../../.kiro/specs/zone-generator-edits/tasks.md) (rule edit interpreter) |
| [P-9-Req-4](#p-9-req-4) | [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) (budgets), [step 19](../../../.kiro/specs/zone-generator-quality/tasks.md) (Draws) |
| [P-9-Req-5](#p-9-req-5) | [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) (loopback and CORS), [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 6 |
| [P-9-Req-6](#p-9-req-6) | [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 6 |
| [P-9-Req-7](#p-9-req-7) | every slice |
| [P-9-Req-8](#p-9-req-8) | [step 28](../../../.kiro/specs/test-speed/tasks.md) |
| [P-9-Req-9](#p-9-req-9) | project-docs (task 5, planned) |
| [P-9-Req-10](#p-9-req-10) | none |
| [P-9-Req-11](#p-9-req-11) | project-docs (task 4, planned) |
| [P-9-Req-12](#p-9-req-12) | none |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) | [`zone-generator-m0-hygiene`](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) | done 2026-10-21 | 99 | The Hypothesis property suite; the cave pipeline and the old Flask viewer deleted; loopback bind and CORS; the gate made sound; agents pointed at spec `tasks.md` files |
| 28 | [`test-speed`](../../../.kiro/specs/test-speed/tasks.md) | done 2026-11-25 | 15 | The suite in tiers; the `gate` marker and the `quick` profile; the full run cut from 3308 s to 1323 s |
| project-docs | [`project-docs`](../../../.kiro/specs/project-docs/tasks.md) | in progress | 1 or more | Pillars, [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md), [`OPEN.md`](../../../OPEN.md), a one-page roadmap, tooling |

Also served by: [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 6 (output confinement; P-2), [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) ([`scripts/stage.py`](../../../scripts/stage.py); P-8), and
the worktree tooling and card format, which landed as integration commits outside any slice.
