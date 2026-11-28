# P-7 Engaging every time — plan

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

## Goal

Every zone is composed, varied and paced, not a random scatter: a clear entrance, a climax,
loops, solvable locks, distinct areas joined at deliberate crossings, rooms that hold things,
and a gate that redraws a dull layout the way it redraws an unwalkable one, saying plainly when
the best it found still falls short.

## Scope

- Layout: the two engines ([`generators/layout.py`](../../../generators/layout.py), [`layout_engine.py`](../../../generators/layout_engine.py), [`generators/topology/`](../../../generators/topology),
  [`rules/topology/`](../../../rules/topology)), elevation and Levels, sizing, placement, hall length.
- Pacing and gating ([`layout.py`](../../../generators/layout.py)), Districts ([`generators/districts.py`](../../../generators/districts.py)).
- What a room holds: Features, POIs, Scales, Transitions ([`room_layouts.py`](../../../generators/room_layouts.py), [`room_scales.py`](../../../generators/room_scales.py),
  [`transitions.py`](../../../generators/transitions.py), [`rules/rooms/`](../../../rules/rooms)).
- Wilderness Sites ([`generators/sites/`](../../../generators/sites), [`rules/sites/`](../../../rules/sites)) and the outdoor dungeon's composition
  ([`outdoor_dungeon.py`](../../../generators/outdoor_dungeon.py), [`envelope.py`](../../../generators/envelope.py)).
- The quality meter and its bands ([`generators/quality.py`](../../../generators/quality.py), [`scripts/quality_sweep.py`](../../../scripts/quality_sweep.py)).

## Non-goals

- Surfaces, wall shapes and decor models (P-5); whether it's walkable (P-2).
- A full mission-graph grammar (the approach from Joris Dormans' work on generated game levels): EverQuest gates by depth and danger, not by chains of locks.
- Pacing or gates in geometry: they stay advisory in the sidecar.

## Requirements

| ID | Requirement | Parent | Status now |
|---|---|---|---|
| <a id="p-7-req-1"></a>P-7-Req-1 | A composed, solvable layout: an entrance, a climax, locks that can always be opened | [ZG-Req-21](../../../.kiro/specs/zone-generator/requirements.md#requirement-21-composed-solvable-layout) | Built (the pre-spec layout, pacing and gating; on Graph layouts the climax is the rules' `deep` room) |
| <a id="p-7-req-2"></a>P-7-Req-2 | Topology control: linear, branching or looped, chosen by a control or by words ("maze", "linear") | [ZG-Req-22](../../../.kiro/specs/zone-generator/requirements.md#requirement-22-topology-control) | **Never built.** No slice served it: the plan has no `topology` field, and `set_topology` exists only as an unsupported edit op. The Layout (classic or graph) and Rule set controls are the nearest levers ([P-7-1](OPEN.md#p-7-1)) |
| <a id="p-7-req-3"></a>P-7-Req-3 | Districts: 2 or 3 distinct areas joined at deliberate crossings | [ZG-Req-23](../../../.kiro/specs/zone-generator/requirements.md#requirement-23-districts) | Built ([step 20](../../../.kiro/specs/zone-generator-districts/tasks.md)), each with its own look ([step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md)) and its own race, intrusion and drops ([step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md)). Off by default ([P-7-2](OPEN.md#p-7-2)) |
| <a id="p-7-req-4"></a>P-7-Req-4 | A quality gate redraws dull layouts | [ZG-Req-24](../../../.kiro/specs/zone-generator/requirements.md#requirement-24-quality-gate) | Built ([step 19](../../../.kiro/specs/zone-generator-quality/tasks.md)): 11 metrics, with bands set from about 24,000 of the generator's own Draws |
| <a id="p-7-req-5"></a>P-7-Req-5 | A degraded build always says so | [ZG-Req-25](../../../.kiro/specs/zone-generator/requirements.md#requirement-25-quality_degraded-is-always-visible) | Built ([step 19](../../../.kiro/specs/zone-generator-quality/tasks.md)): in the sidecar, the responses, the warnings, a banner and the metrics list |

## Traceability

Which slices served each requirement. ([`scripts/task_status.py`](../../../scripts/task_status.py)
will generate this table after [project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md).)

| Requirement | Served by |
|---|---|
| [P-7-Req-1](#p-7-req-1) | pre-spec layout, pacing and gating; steps [6](../../../.kiro/specs/zone-generator-graph-layout/tasks.md) and [7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) (Graph layouts, Levels) |
| [P-7-Req-2](#p-7-req-2) | none |
| [P-7-Req-3](#p-7-req-3) | steps [20](../../../.kiro/specs/zone-generator-districts/tasks.md), [22](../../../.kiro/specs/zone-generator-district-looks/tasks.md) and [31](../../../.kiro/specs/zone-generator-district-races/tasks.md); [step 32](../../../.kiro/specs/zone-generator-races-followups/tasks.md) (in progress) |
| [P-7-Req-4](#p-7-req-4) | [step 19](../../../.kiro/specs/zone-generator-quality/tasks.md) |
| [P-7-Req-5](#p-7-req-5) | [step 19](../../../.kiro/specs/zone-generator-quality/tasks.md) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Layout, pacing, gating, and the first content layer (pre-spec, [ROADMAP](../../../ROADMAP.md#layout--pacing--gating)) | — | done | (before specs) | TinyKeep; roles read off the room graph; solvable locks; Purpose × race × Element |
| (the follow-up runway) | [`zone-generator-followup`](../../../.kiro/specs/zone-generator-followup/tasks.md) | retired, its tasks moved into steps [5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md), [6](../../../.kiro/specs/zone-generator-graph-layout/tasks.md) and [7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) | 1 | The Envelope, the gate learning connectors, the `LayoutEngine` seam |
| 5 | [`zone-generator-outdoor-dungeon`](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md) | done 2026-11-03 | 29 | A hillside dungeon in a compact wilderness, inside a 3D Envelope |
| 6 | [`zone-generator-graph-layout`](../../../.kiro/specs/zone-generator-graph-layout/tasks.md) | done 2026-11-04 | 59 | Graph rewriting from TOML rule sets; the default layout |
| 7 | [`zone-generator-dungeon-verticality`](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) | done 2026-11-06 | 55 | Levels, stairs, Bridges; rooms sized from the race's body height |
| 9 | [`zone-generator-room-layouts`](../../../.kiro/specs/zone-generator-room-layouts/tasks.md) | done 2026-11-07 | 55 | Features and POIs; Scales from layered rules; Transitions |
| 10 | [`zone-generator-wilderness-pois`](../../../.kiro/specs/zone-generator-wilderness-pois/tasks.md) | done 2026-11-08 | 45 | Sites: camps, huts, farmsteads, watchtowers, shrines, ruins |
| 13 | [`zone-generator-site-sockets`](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) | done 2026-11-14 | 38 | Sites on point Sockets in Groups, clustered as stock |
| 19 | [`zone-generator-quality`](../../../.kiro/specs/zone-generator-quality/tasks.md) | done 2026-11-18, acceptance skipped | 15 | The quality meter, bands and soft gate |
| 20 | [`zone-generator-districts`](../../../.kiro/specs/zone-generator-districts/tasks.md) | done 2026-11-19, acceptance skipped | 23 | Districts with Purposes, palettes, light, climaxes, Thresholds |
| 22 | [`zone-generator-district-looks`](../../../.kiro/specs/zone-generator-district-looks/tasks.md) | done 2026-11-20, acceptance skipped | 27 | Each District's walls and decor follow its Purpose |
| 27 | [`zone-generator-random-placement`](../../../.kiro/specs/zone-generator-random-placement/tasks.md) | done 2026-11-25 | 49 | Cave and outdoor rooms off the lattice; stock room-size spread everywhere |
| 30 | [`zone-generator-hall-length`](../../../.kiro/specs/zone-generator-hall-length/tasks.md) | done 2026-11-26 | 22 | The Hall length scalar and slider |
| 31 | [`zone-generator-district-races`](../../../.kiro/specs/zone-generator-district-races/tasks.md) | done 2026-11-27 | 58 | A race per District, intruder Districts, one-way drops, map layers |
| 32 | [`zone-generator-races-followups`](../../../.kiro/specs/zone-generator-races-followups/tasks.md) | paused for [step 33](../../../.kiro/specs/zone-generator-layout-repair/tasks.md) (task 2 done) | 4 | Breach rate, map returns, same seed same build |

Also served by: [step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md) (room kinds shown through wall shapes; P-5), [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) (Sites attach to
Sockets; P-8), [step 33](../../../.kiro/specs/zone-generator-layout-repair/tasks.md) (contact scoring for breaches; P-2).

With P-5 this pillar holds most of the project's work since [step 5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md) (14 slices, about 480
commits). Its [P-7-Req-2](#p-7-req-2) (topology control) is the one requirement in the pillar no slice touched.
