# P-E EverQuest look and feel — plan

## Goal

A generated zone is indistinguishable from a hand-crafted Classic–PoP zone: scale, triangle
size, palette, textures, wall shapes, stairs, water and the stuff in rooms all measured from
real zones, with conformance measured rather than claimed.

## Scope

- Measurement of stock zones (`analyzer/`, `styles/*.json`, the `scripts/*_survey.py` scripts).
- Textures (`generators/textures/`) and the textured preview.
- Wall styles (`generators/wall_styles.py`, `rules/walls/`), winding tunnels, cave clumps.
- Decor: stock Props from the user's install (`generators/decor/`, `rules/decor/`).
- The wilderness landscape and trees (`generators/wilderness/`, `generators/vegetation/`).
- The `cave` Purpose and its dressing.

## Non-goals

- Layout composition, pacing, Districts, Sites placement (P-G).
- Bespoke trained mesh models (ROADMAP "NOT doing").
- Later-era (`.eqg`-only) art as the default look: Classic–PoP is the default.

## Requirements (umbrella IDs)

| ID | Requirement | Status now |
|---|---|---|
| P-E.15 | Era fidelity and measured conformance against real zones of the same type | Half built: style profiles drive scale, and textures are graded toward each theme's measured Look_Stats (step 4). The per-zone **ConformanceReport** (`analyzer/conformance.py`, Property 38) was never built (OPEN E-2) |
| P-E.16 | Procedural normal maps for every material | Not built: deferred at step 4 because Classic–PoP zones have none and the user chose the classic look (OPEN E-1) |
| P-E.17 | Textured preview | Diffuse half built (step 3); the normal half waits on 16 |
| P-E.33 | The `cave` Purpose of a dungeon | Built (step 21), but **the requirement's text was never written** into the umbrella requirements; it is cited by number only (OPEN X-18) |
| P-B.7 | Natural geometry style (filed under P-B) | Served here by the `rough` wall style (step 8) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Phase 0, Classic–PoP profiles (pre-spec) | — | done | (pre-spec) | Style metrics from the install; profiles from Guk, Sebilis, Faydark and more |
| Textures, terrain (pre-spec) | — | done | (pre-spec) | Procedural seamless textures, AI drop-in; eroded heightfield |
| 1 | [`zone-generator-wilderness`](../../../.kiro/specs/zone-generator-wilderness/tasks.md) | done 2026-10-29 | 54 | Karana-like open wilderness: Design_Matrix, erosion, cliffs, water, lava, bowl |
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

Also served by: step 9 (Features in each wall style's form; P-G), step 22 (District looks; P-G).

This is the largest pillar by commits. Steps 21–29 were mostly cave look; normal maps and the
conformance report, the two requirements that measure the look, were never picked up.
