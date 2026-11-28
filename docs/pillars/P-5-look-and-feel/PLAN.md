# P-5 EverQuest look and feel — plan

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

## Goal

A generated zone is indistinguishable from a hand-crafted Classic–PoP zone: scale, triangle
size, palette, textures, wall shapes, stairs, water and the stuff in rooms all measured from
real zones, with conformance measured rather than claimed.

## Scope

- Measurement of stock zones ([`analyzer/`](../../../analyzer), `styles/*.json`, the `scripts/*_survey.py` scripts).
- Textures ([`generators/textures/`](../../../generators/textures)) and the textured preview.
- Wall styles ([`generators/wall_styles.py`](../../../generators/wall_styles.py), [`rules/walls/`](../../../rules/walls)), winding tunnels, cave clumps.
- Decor: stock Props from the user's install ([`generators/decor/`](../../../generators/decor), [`rules/decor/`](../../../rules/decor)).
- The wilderness landscape and trees ([`generators/wilderness/`](../../../generators/wilderness), [`generators/vegetation/`](../../../generators/vegetation)).
- The `cave` Purpose and its dressing.

## Non-goals

- Layout composition, pacing, Districts, Sites placement (P-7).
- Bespoke trained mesh models ([ROADMAP "NOT doing"](../../../ROADMAP.md#deliberately-not-doing-and-why)).
- Later-era (`.eqg`-only) art as the default look: Classic–PoP is the default.

## Requirements

| ID | Requirement | Parent | Status now |
|---|---|---|---|
| <a id="p-5-req-1"></a>P-5-Req-1 | Zones match their era, and conformance against real zones of the same type is measured | [ZG-Req-15](../../../.kiro/specs/zone-generator/requirements.md#requirement-15-era-fidelity-and-measured-conformance) | Half built: style profiles drive scale, and textures are graded toward each theme's measured texture statistics ([step 4](../../../.kiro/specs/zone-generator-interesting-textures/tasks.md)). The per-zone conformance report (`ConformanceReport` in a planned `analyzer/conformance.py`, [Property 38](../../../.kiro/specs/zone-generator/design.md#property-38-conformance-is-measured-and-in-range)) was never built ([P-5-2](OPEN.md#p-5-2)) |
| <a id="p-5-req-2"></a>P-5-Req-2 | Procedural normal maps for every material | [ZG-Req-16](../../../.kiro/specs/zone-generator/requirements.md#requirement-16-procedural-normal-maps) | Not built: deferred at [step 4](../../../.kiro/specs/zone-generator-interesting-textures/tasks.md), because Classic–PoP zones have none and the user chose the classic look ([P-5-1](OPEN.md#p-5-1)) |
| <a id="p-5-req-3"></a>P-5-Req-3 | A textured preview in the browser | [ZG-Req-17](../../../.kiro/specs/zone-generator/requirements.md#requirement-17-textured-preview) | The diffuse half is built ([step 3](../../../.kiro/specs/zone-generator-placeholder-textures/tasks.md)); the normal-map half waits on [P-5-Req-2](#p-5-req-2) |
| <a id="p-5-req-4"></a>P-5-Req-4 | The `cave` Purpose of a dungeon | [ZG-Req-33](../../../.kiro/specs/zone-generator/requirements.md#introduction) | Built ([step 21](../../../.kiro/specs/zone-generator-cave/tasks.md)). But the parent's text was never written into the umbrella requirements; it is cited by number only ([P-9-14](../P-9-engineering/OPEN.md#p-9-14)) |

[P-2-Req-4](../P-2-traversable/PLAN.md#p-2-req-4) (a natural geometry style, filed under P-2) is served here, by the `rough` wall style
([step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md)).

## Traceability

Which slices served each requirement. ([`scripts/task_status.py`](../../../scripts/task_status.py)
will generate this table after [project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md).)

| Requirement | Served by |
|---|---|
| [P-5-Req-1](#p-5-req-1) | pre-spec Phase 0 (profiles), [step 4](../../../.kiro/specs/zone-generator-interesting-textures/tasks.md) (texture profiles), steps [7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) and [27](../../../.kiro/specs/zone-generator-random-placement/tasks.md) (stock scale and room-size spread), [step 11](../../../.kiro/specs/zone-generator-room-decor/tasks.md) (stock decor) |
| [P-5-Req-2](#p-5-req-2) | none |
| [P-5-Req-3](#p-5-req-3) | [step 3](../../../.kiro/specs/zone-generator-placeholder-textures/tasks.md) |
| [P-5-Req-4](#p-5-req-4) | [step 21](../../../.kiro/specs/zone-generator-cave/tasks.md), [step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md) (cave Districts), [step 29](../../../.kiro/specs/zone-generator-cave-clumps/tasks.md) (cave clumps) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Phase 0, Classic–PoP profiles (pre-spec, [ROADMAP](../../../ROADMAP.md#phase-0--zone-analyzer)) | — | done | (before specs) | Style metrics from the install; profiles from Guk, Sebilis, Faydark and more |
| Textures, terrain (pre-spec, [ROADMAP](../../../ROADMAP.md#textures)) | — | done | (before specs) | Procedural seamless textures, AI drop-in; eroded heightfield |
| 1 | [`zone-generator-wilderness`](../../../.kiro/specs/zone-generator-wilderness/tasks.md) | done 2026-10-29 | 54 | An open wilderness like the Karana plains: Design_Matrix, erosion, cliffs, water, lava, bowl |
| 2 | [`zone-generator-wilderness-trees`](../../../.kiro/specs/zone-generator-wilderness-trees/tasks.md) | done 2026-11-01 | 26 | Generated low-poly trees in groves |
| 3 | [`zone-generator-placeholder-textures`](../../../.kiro/specs/zone-generator-placeholder-textures/tasks.md) | done 2026-11-01 | 26 | Named materials, placeholder painter, textured GLB, EQ UV convention |
| 4 | [`zone-generator-interesting-textures`](../../../.kiro/specs/zone-generator-interesting-textures/tasks.md) | done 2026-11-01 | 25 | Measured texture profiles, recipe painters, texel density |
| 8 | [`zone-generator-room-walls`](../../../.kiro/specs/zone-generator-room-walls/tasks.md) | done 2026-11-07 | 31 | `built`, `hewn`, `rough` wall styles as Outlines inside each room's Box |
| 11 | [`zone-generator-room-decor`](../../../.kiro/specs/zone-generator-room-decor/tasks.md) | done 2026-11-12 | 92 | 4,651 stock models catalogued and tagged; recipes place them where the gate agrees |
| 15 | [`zone-generator-decor-rules`](../../../.kiro/specs/zone-generator-decor-rules/tasks.md) | done 2026-11-15 | 26 | Decor rules as base plus drop-in layers; the room view |
| 21 | [`zone-generator-cave`](../../../.kiro/specs/zone-generator-cave/tasks.md) | done 2026-11-20, acceptance skipped | 28 | The `cave` Purpose: room types, cold light, damp rock, rough walls, smaller rooms |
| 23 | [`zone-generator-winding-tunnels`](../../../.kiro/specs/zone-generator-winding-tunnels/tasks.md) | done 2026-11-20 | 29 | Rough corridors' plain legs wind at angles from 113 stock tunnels |
| 24 | [`zone-generator-flooded-rooms`](../../../.kiro/specs/zone-generator-flooded-rooms/tasks.md) | done 2026-11-21, look skipped | 4 | Water fills a flooded room to its walls at 0.6 H |
| 25 | [`zone-generator-winding-routes`](../../../.kiro/specs/zone-generator-winding-routes/tasks.md) | done 2026-11-21 | 24 | One winding centreline door to door |
| 26 | [`zone-generator-winding-control`](../../../.kiro/specs/zone-generator-winding-control/tasks.md) | done 2026-11-22 | 29 | The Winding scalar and slider; cave rooms off the lattice |
| 29 | [`zone-generator-cave-clumps`](../../../.kiro/specs/zone-generator-cave-clumps/tasks.md) | done 2026-11-25, look skipped | 19 | Cave rooms open into each other through throats and clump |

Also served by: [step 9](../../../.kiro/specs/zone-generator-room-layouts/tasks.md) (Features in each wall style's form; P-7), [step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md) (District looks; P-7).

This is the largest pillar by commits. Steps [21](../../../.kiro/specs/zone-generator-cave/tasks.md)–[29](../../../.kiro/specs/zone-generator-cave-clumps/tasks.md) were mostly cave look; normal maps and the
conformance report, the two requirements that measure the look, were never picked up.
