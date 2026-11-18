# Archive — zone-generator-edits

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-18 by the lead: the user chose "Rest of m4" for step 18 and the lead chose the
shape. The user confirms the choice and these decisions at the first look (task 9).

1. **The history is the zone's versions** (amendment A1): no in-memory Session store; an edit is
   a rebuild whose change is a list of ops, written as the next version with an `edit` block.
2. **Undo and redo walk parent links on the page** (A2): undo opens the parent, redo the newest
   child; no server call and no file changes.
3. **Vocabulary in two stages** (A3): the ops the saved spec takes without planning again land
   first; resize follows task 2's grounding; the rest are "not yet supported".
4. **An edit's `how` is honest:** a partial edit that changes the TER is caught by `StaleStages`
   and built in full; either way the version equals a full build of the edited spec.
5. **Per-zone build lock:** a second edit or rebuild on a zone while one builds is a 429.

## Follow-ups
