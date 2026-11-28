# P-4 True-layout artifacts — plan

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

## Goal

The maps match the walls the player walks along. Alongside the 3D view, the page offers a
top-down map traced from the real mesh and an EverQuest in-client map file, both viewable and
downloadable with every other build file.

## Scope

- Outline extraction from the built TER ([`generators/mapgeom.py`](../../../generators/mapgeom.py)).
- The in-client map files `maps/<name>.txt` and layers `_1`..`_3` (`generators/eqmap.py`).
- The SVG map with its annotations and layers ([`generators/mapview.py`](../../../generators/mapview.py)).
- The Files panel and download routes ([`web/src/artifacts.ts`](../../../web/src/artifacts.ts), [`server/app.py`](../../../server/app.py) build-file routes).
- Map overlays the page draws on top (Socket markers, edit tints).

## Non-goals

- What the map says about pacing or Districts as design (P-7 owns those; this pillar draws them).
- Proving the map in the client's map window: that waits on an Export loaded in the client (P-3,
  [umbrella decision 21](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part c).

## Requirements

| ID | Requirement | Parent | Status now |
|---|---|---|---|
| <a id="p-4-req-1"></a>P-4-Req-1 | The map outline is traced from the built mesh | [ZG-Req-12](../../../.kiro/specs/zone-generator/requirements.md#requirement-12-mesh-derived-outline) | Built ([step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md)): floor faces signed so a ceiling never counts, the floor's edge found by exact interval coverage, wall and ledge classes |
| <a id="p-4-req-2"></a>P-4-Req-2 | An EverQuest in-client map file | [ZG-Req-13](../../../.kiro/specs/zone-generator/requirements.md#requirement-13-everquest-in-client-map-file) | Built ([step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md)): a convention tested against stock maps (negate and swap), a writer and a parser (all 143 stock maps parse), up to 4 depth bands as layers. Not yet seen in the client |
| <a id="p-4-req-3"></a>P-4-Req-3 | The true-layout map and every build file are in the browser | [ZG-Req-14](../../../.kiro/specs/zone-generator/requirements.md#requirement-14-true-layout-map-and-artifacts-in-the-web_app) | Built ([step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md)): the Files panel (SVG, 2× PNG, `.txt`, `.eqg`, bundle). [Step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) added layers to show and hide, and an EQ-map view |

## Traceability

Which slices served each requirement. ([`scripts/task_status.py`](../../../scripts/task_status.py)
will generate this table after [project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md).)

| Requirement | Served by |
|---|---|
| [P-4-Req-1](#p-4-req-1) | [step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md); step [9](../../../.kiro/specs/zone-generator-room-layouts/tasks.md) and [10](../../../.kiro/specs/zone-generator-wilderness-pois/tasks.md) fixes (face order) |
| [P-4-Req-2](#p-4-req-2) | [step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md), [step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) (a band per stacked Level) |
| [P-4-Req-3](#p-4-req-3) | [step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md), [step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) (the SVG frame), [step 18](../../../.kiro/specs/zone-generator-edits/tasks.md) (edit tint), [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) (layers) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Top-down map (pre-spec, [ROADMAP](../../../ROADMAP.md#done)) | — | done | (before specs) | Spec-derived schematic SVG and web modal |
| 1b | [`zone-generator-m2-true-layout-artifacts`](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md) | done 2026-10-31 | 35 | Outline from the mesh, EQ map files, outline layer, artifact routes, Files panel |

Also served by: [step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) (a map band per stacked Level; P-7), [step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) (the SVG carries its frame
for Socket markers; P-7), [step 18](../../../.kiro/specs/zone-generator-edits/tasks.md) (edit tint overlay; P-6), [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) (map layers, EQ-map view;
P-7). [Step 32](../../../.kiro/specs/zone-generator-races-followups/tasks.md) task 3 (the map's return marks from the layout) is in flight.

This pillar has been quiet since [step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md): one slice, and map work since then rode inside other
pillars' steps.
