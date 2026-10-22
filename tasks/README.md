# Tasks

> **This board is history.** Kiro specs replace it (umbrella design,
> "Planning Model"): new work goes in `.kiro/specs/<feature>/tasks.md`, under a
> milestone spec of `.kiro/specs/zone-generator/`. Done task files stay here as
> a record. Open ones are absorbed into a milestone or become a follow-on spec
> (umbrella design, "Scope of open task files"), and are retired when that
> milestone lands. This index is kept until nothing open remains.

One file per task, each with subtasks, acceptance criteria and deliverables.

- `Status` values: `not-started` · `in-progress` · `blocked` · `done` ·
  `absorbed` (the work moved into a milestone spec).
- Keep this index's status column in sync with each task file's `Status:` line.

See also: `ROADMAP.md` (status and priorities), `docs/ACCEPTANCE.md` (how to
validate), `docs/RESEARCH.md` (decisions and investigations).

## Board

| Task | Status | Where it goes | Epic |
|------|--------|---------------|------|
| [content-layer-dungeon](content-layer-dungeon.md) | done | — | Content layer Step 1: single-district dungeon themes (archetype × race × tint) |
| [corridor-connection](corridor-connection.md) | done | — | Box-backend geometry correctness: Z/L/straight corridor routing, grade-capped elevation on subdivided ramps. Validated under the gate later found unsound; the suite re-ran green after the M0 fix |
| [traversability-validator](traversability-validator.md) | done | — | Automated "can a player reach every room?" mesh walk. Adjacency made sound in M0 |
| [validate-in-pipeline](validate-in-pipeline.md) | done | — | Validator gates generate (server + CLI) with fresh-seed retry, timeout and failure log |
| [web-seed-input](web-seed-input.md) | done | — | Seed input + "reproduce" in the viewer; seed-determinism fix |
| [cave-backend-refactor](cave-backend-refactor.md) | absorbed | M0 | Cave rebuild part 1: superseded, the cave pipeline was deleted outright |
| [cave-cavify-dungeon](cave-cavify-dungeon.md) | absorbed | M5 | Cave rebuild part 2: becomes the natural geometry style |
| [web-controls-generate](web-controls-generate.md) | not-started | M1 | Controls panel as a first-class driver with its own Generate button |
| [eq-map-export](eq-map-export.md) | not-started | M2 | In-client EQ map files from the real mesh |
| [web-svg-mesh-outline](web-svg-mesh-outline.md) | not-started | M2 | Mesh-traced outline layer on the web map (shares the extractor) |
| [content-layer-districts](content-layer-districts.md) | not-started | M3 | Content layer Step 2: districts |
| [layout-topology-control](layout-topology-control.md) | not-started | M3 | Topology lever in `_connect_rooms` |
| [multi-level-dungeon](multi-level-dungeon.md) | not-started | follow-on spec, after M3 | True stacked floors with vertical connectors |
| [layout-oneway-connections](layout-oneway-connections.md) | not-started | follow-on spec, after M6 | Directed (one-way) connections |

The former backlog (refinement, SQL export, doorway-fit, water zones, normal
maps) is now planned in the umbrella Delivery plan and tracked in `ROADMAP.md`.
