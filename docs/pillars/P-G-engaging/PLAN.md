# P-G Engaging every time — plan

## Goal

Every zone is composed, varied and paced, not a random scatter: a clear entrance, a climax,
loops, solvable locks, distinct areas joined at deliberate crossings, rooms that hold things,
and a gate that redraws a dull layout the way it redraws an unwalkable one, saying plainly when
the best it found still falls short.

## Scope

- Layout: the two engines (`generators/layout.py`, `layout_engine.py`, `generators/topology/`,
  `rules/topology/`), elevation and Levels, sizing, placement, hall length.
- Pacing and gating (`layout.py`), Districts (`generators/districts.py`).
- What a room holds: Features, POIs, Scales, Transitions (`room_layouts.py`, `room_scales.py`,
  `transitions.py`, `rules/rooms/`).
- Wilderness Sites (`generators/sites/`, `rules/sites/`) and the outdoor dungeon's composition
  (`outdoor_dungeon.py`, `envelope.py`).
- The quality meter and its bands (`generators/quality.py`, `scripts/quality_sweep.py`).

## Non-goals

- Surfaces, wall shapes and decor models (P-E); whether it's walkable (P-B).
- A full mission-graph grammar (Dormans): EQ gates by depth and danger, not lock chains.
- Pacing or gates in geometry: they stay advisory in the sidecar.

## Requirements (umbrella IDs)

| ID | Requirement | Status now |
|---|---|---|
| P-G.21 | Composed, solvable layout: entrance, climax, solvable locks | Built (pre-spec layout, pacing, gating; on Graph layouts the climax is the rules' `deep` room) |
| P-G.22 | Topology control: linear, branching or looped, chosen by control or words ("maze", "linear") | **Never built.** No slice served it: there is no `topology` field on the plan; `set_topology` exists only as an unsupported edit op. The Layout (classic/graph) and Rule set controls are the nearest levers (OPEN G-1) |
| P-G.23 | Districts: 2–3 distinct areas joined at deliberate crossings | Built (step 20), each with its own look (step 22) and race, intrusion and drops (step 31); off by default (OPEN G-2) |
| P-G.24 | Quality gate: dull layouts redrawn | Built (step 19): 11 metrics, bands from ~24k of the generator's own Draws |
| P-G.25 | Quality_Degraded is always visible | Built (step 19): sidecar, responses, warnings, banner and metrics list |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Layout, pacing, gating, content step 1 (pre-spec) | — | done | (pre-spec) | TinyKeep; graph-derived roles; solvable locks; archetype × race × tint |
| (runway) | [`zone-generator-followup`](../../../.kiro/specs/zone-generator-followup/tasks.md) | retired, dispersed into steps 5–7 | 1 | Envelope, gate-learns-connectors, LayoutEngine seam |
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
| 32 | [`zone-generator-races-followups`](../../../.kiro/specs/zone-generator-races-followups/tasks.md) | paused for step 33 (task 2 done) | 4 | Breach rate, map returns, same seed same build |

Also served by: step 8 (room kinds shown through wall shapes; P-E), step 12 (Sites attach to
Sockets; P-H), step 33 (contact scoring for breaches; P-B).

With P-E this pillar holds most of the project's work since step 5 (14 slices, about 480
commits); its own Requirement 22 is the one requirement in the pillar no slice touched.
