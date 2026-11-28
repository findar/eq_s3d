# P-D True-layout artifacts — plan

## Goal

The maps match the walls the player walks along. Alongside the 3D view, the page offers a
top-down map traced from the real mesh and an EverQuest in-client map file, both viewable and
downloadable with every other build file.

## Scope

- Outline extraction from the built TER (`generators/mapgeom.py`).
- The in-client map files `maps/<name>.txt` and layers `_1`..`_3` (`generators/eqmap.py`).
- The SVG map with its annotations and layers (`generators/mapview.py`).
- The Files panel and download routes (`web/src/artifacts.ts`, `server/app.py` build-file routes).
- Map overlays the page draws on top (Socket markers, edit tints).

## Non-goals

- What the map says about pacing or Districts as design (P-G owns those; this pillar draws them).
- Proving the map in the client's map window: that waits on an Export loaded in the client (P-C,
  umbrella decision 21c).

## Requirements (umbrella IDs)

| ID | Requirement | Status now |
|---|---|---|
| P-D.12 | Mesh-derived outline | Built (step 1b): signed Floor_Faces, a geometric Floor_Boundary by exact interval coverage, wall and ledge classes |
| P-D.13 | EverQuest in-client map file | Built (step 1b): grounded convention (negate + swap), writer and parser (all 143 stock maps parse), up to 4 depth bands as layers. Not seen in the client yet |
| P-D.14 | True-layout map and every build file in the browser | Built (step 1b): Files panel (SVG, 2× PNG, `.txt`, `.eqg`, bundle); step 31 added show/hide layers and an EQ-map view |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Top-down map (pre-spec) | — | done | (pre-spec) | Spec-derived schematic SVG and web modal |
| 1b | [`zone-generator-m2-true-layout-artifacts`](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md) | done 2026-10-31 | 35 | Outline from the mesh, EQ map files, outline layer, artifact routes, Files panel |

Also served by: step 7 (a map band per stacked Level; P-G), step 13 (the SVG carries its frame
for Socket markers; P-G), step 18 (edit tint overlay; P-F), step 31 (map layers, EQ-map view;
P-G). Step 32 task 3 (the map's return marks from the layout) is in flight.

This pillar has been quiet since step 1b: one slice, and map work since then rode inside other
pillars' steps.
