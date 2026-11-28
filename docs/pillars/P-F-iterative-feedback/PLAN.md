# P-F Iterative feedback — plan

## Goal

A user refines the zone they have instead of starting over: "make the boss room bigger",
"reroll the decor", "undo that". An edit changes only what was asked, never leaves a broken zone,
and every version stays reachable.

## Scope

- Versions of a zone (`output/web/<zone>/v<n>/`, parent links) and the version stepper.
- Rerolls and partial rebuilds from saved stages (`generators/rebuild.py`).
- Chat edits: interpretation (`ai/edits.py`, `ai/llm_edits.py`), application
  (`generators/edits.py`, `generators/resize.py`), the Feedback box (`web/src/feedback.ts`).
- Undo and redo.
- Keeping one room's decor from the room view ("Use in zone").

## Non-goals

- Server-side sessions, TTLs and eviction: dropped by decision 37 (the versions on disk are the
  history).
- Editing rule recipes from the page (OPEN F-7 is a candidate, not in scope yet).

## Requirements (umbrella IDs, as amended by decisions 35 and 37)

| ID | Requirement | Status now |
|---|---|---|
| P-F.18 | Sessions and feedback interpretation | Built as versions (A1: no Session store): text → ops by a rule interpreter, an LLM optional with the rules as fallback |
| P-F.19 | Edit application and acceptance: only what was asked changes; a failing edit is not applied | Built for purpose, locks, room and decor rerolls, decor level, regenerate and four resizes. Six ops answer "not yet supported" (OPEN F-1) |
| P-F.20 | History, undo and redo | Built: undo opens the parent version, redo the newest child, on the page with no server call; an edit from an older version branches |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| 16 | [`zone-generator-partial-rebuild`](../../../.kiro/specs/zone-generator-partial-rebuild/tasks.md) | done 2026-11-17 | 19 | A reroll is the next version; decor rebuilds from the parent's saved stages, byte-identical to a full build |
| 18 | [`zone-generator-edits`](../../../.kiro/specs/zone-generator-edits/tasks.md) | done 2026-11-18, acceptance skipped | 22 | Chat edits on versions; undo and redo along parent links |

Also served by: step 12 (the stage hand-offs that make partial rebuild possible; P-H), step 15
(the room view and its "Use in zone"; P-E), step 19 (an edit outside the quality bands is built
and marked `edit_outside_bands`; P-G).

Nothing here has been looked at in person: both slices skipped their acceptance pass.
