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
| [content-layer-dungeon](content-layer-dungeon.md) | in-progress | Content / semantic layer — Step 1 built (needs 3D eyeball); Step 2 districts is the next build |

## Backlog (not yet broken into task files)

Pulled from ROADMAP "Next" / design-captured; promote to a task file when started.

- Iterative refinement (chat loop + partial regen) — ROADMAP "Next" #2
- EQEmu SQL export + in-engine validation — ROADMAP "Next" #3 (capstone)
- Cave rebuild — "cavify the dungeon layout" (shelved; after the ordered priorities)
- Doorway-fit for gates; water/mixed-environment zones; outdoor rooms as places;
  procedural normal maps
