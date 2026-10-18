# Tasks

The **tactical** task board: one file per task, each with subtasks, acceptance
criteria, and deliverables. This is the tier below `ROADMAP.md` (which tracks
epics/priorities). An agent working a task opens its file, updates the checkboxes
and status as it goes, and records commit hashes under Deliverables.

- New task → copy `_TEMPLATE.md` to `tasks/<task-id>.md`, fill it in, add a row below.
- Keep this index's status column in sync with each task file's `Status:` line.
- `Status` values: `not-started` · `in-progress` · `blocked` · `done`.
- Done tasks stay here for history (don't delete), status `done`.

See also: `ROADMAP.md` (why / priority order), `docs/ACCEPTANCE.md` (how to
validate), `docs/RESEARCH.md` (decisions & investigations).

## Board

| Task | Status | Epic |
|------|--------|------|
| [content-layer-dungeon](content-layer-dungeon.md) | in-progress | Content / semantic layer — Step 1 built; navigability measured (sound, but sign-off blocked on corridor-connection — sink exposes it); aesthetic 3D eyeball + Step 2 districts remain |
| [corridor-connection](corridor-connection.md) | not-started | Box-backend geometry correctness — same-axis room pairs need a 3-segment Z-corridor (ramps + stairs); plus elevation-steepness (unwalkable cliffs / oversized steps) |
| [traversability-validator](traversability-validator.md) | done | Validation tooling — automated "can a player reach every room?" mesh walk (dungeon/box backend); CLI + seed-sweep suite. Outdoor/cave deferred (mesh/graph coord-frame mismatch). Pending one 3D eyeball |
| [cave-backend-refactor](cave-backend-refactor.md) | not-started | Cave rebuild (1/2) — park the broken independent cave backend and isolate cave-specific logic behind a clean geometry-backend seam; no new capability |
| [cave-cavify-dungeon](cave-cavify-dungeon.md) | not-started | Cave rebuild (2/2) — rebuild `cave` as an organic-styling transform of the validated box/dungeon geometry; must pass the traversability validator |
| [web-seed-input](web-seed-input.md) | done | Web viewer UX — seed input + "⟳ reproduce" shipped so a human can reproduce/walk a specific seed in 3D. Also fixed a determinism bug (cave/outdoor were seeded from the timestamped name, not the seed). Pending one human 3D spot-check |
| [validate-in-pipeline](validate-in-pipeline.md) | not-started | Validation tooling — bake the traversability validator into generate (server + CLI) via a shared generate-validate-retry helper with timeout + structured failure logging; never serve an invalid zone |
| [multi-level-dungeon](multi-level-dungeon.md) | not-started | Box-backend verticality — true stacked floors (rooms directly above each other + vertical connectors) driven by a "levels" control. New capability; follows corridor-connection, gated by the traversability validator |

## Backlog (not yet broken into task files)

Pulled from ROADMAP "Next" / design-captured; promote to a task file when started.

- Iterative refinement (chat loop + partial regen) — ROADMAP "Next" #2
- EQEmu SQL export + in-engine validation — ROADMAP "Next" #3 (capstone)
- Cave rebuild — "cavify the dungeon layout" (shelved; after the ordered priorities)
- Doorway-fit for gates; water/mixed-environment zones; outdoor rooms as places;
  procedural normal maps
