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
6. **Resize lands, all four ops (task 2).** Floors stay put. Scale the room's box about its centre,
   move each touching corridor's end on the room by the wall's shift (keeping its cross position),
   then re-run `wall_styles.apply_walls`/`apply_walls_by_finish` and `room_layouts.apply_features`
   at `rooms_seed or seed`, keeping each Transition's saved look. A full rebuild re-dresses the
   saved spec unchanged only with that look kept. Clamp by bisection: no new 3D overlap, the door
   stays on its wall, the route and its leg directions stay the same, the grade stays at or under
   max(0.5, the old grade), a stair or bridge keeps its layout, and the room stays as tall as its
   corridors. Neighbours can change too. Put them in the Affected_Set: a room whose
   `geometry._door_openings` or `_bridge_slots` change, and a corridor whose `bridge_layout` or
   `stair_layout` change. In 162 resized builds that prediction matched the built triangles every time.
7. **Op parameters (task 1, `ai/edits.py`).** Resize ops take `by`, the fraction of the room's size
   added or taken away (widen and taller 0.1–1.0, default 0.25; narrow 0.05–0.5 and lower
   0.05–0.4, default 0.2); task 7 converts it to task 2's scale factor. Out-of-range values are
   clamped (Req 1.1), not rejected. `remove_lock` with no target removes every lock;
   `set_verticality` takes `level` or `delta`. `validate` returns bad ops with `why`: `schema`
   (invalid, `applied: false` per umbrella 18.9) or `target` (a rejection note, the rest
   apply, 18.5). Every op is recognised there; which apply is `generators/edits.py`'s call.

## Follow-ups
