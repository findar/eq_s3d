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
8. **The edit engine (task 3, `generators/edits.py`).** `apply_edits(doc, ops, seed, version)`
   returns `EditResult(doc, affected_rooms, affected_corridors, notes, how, changed, applied,
   rejected, seed)`; `.affected` is the sidecar's `{rooms, corridors}`. `how` is `partial` when
   every applied op is, `full` when any is (`regenerate`, resize), `None` when nothing applied
   (the route's `applied: false`). `changed` lists the spec fields touched, in op order.
   `applied` carries any drawn seed (`random.Random(f"{seed}:{version}:{i}")`; a retry passes
   the next seed). Each op is re-checked against the spec as edited so far; one that can't
   apply is a note and the rest still apply. `regenerate` returns the doc unchanged plus
   `.seed` (the route plans again from the parent's request) and skips the edit's other ops.
   `add_lock` locks the target's way in from the entrance, its key before every other lock, a
   `solvable()` check or rejected; `remove_lock` with no target removes every lock. The layout
   and `add_lock` share `layout.gate_*`. Resize goes through `_resize` (task 7 replaces it).
   Every partial op builds byte-identical with the parent's stages and in full (Graph dungeon
   seed 2, city seed 5), so none needs the `StaleStages` fallback today.
9. **Resize (task 7, `generators/resize.py`).** `resize_room(doc, room, op, by)` scales by
   `1 + by` or `1 - by` as decision 6 describes, `how: full`, `changed` `[width, depth]` or
   `[height]`. A clamp's note gives the share applied of the share asked and what blocked more
   ("widened room_6 by 4% of the 25% asked; any more and corr_5 would overlap room_6"). Outdoor
   dungeons refuse resize ("rooms under a hill can't be resized yet"): their Tunnel and hill
   cover were fixed against the original boxes. Decor, lights, regions, lock points and city
   POIs follow the room only in the full rebuild and aren't in the clamp checks: look at them
   at the first look.
10. **The edit route (task 4).** `POST /api/edit {zone, version, text | ops, seed?}` answers 200
   with `applied`, `parent`, `version`, `interpreter`, `text`, `ops` (drawn seeds filled in),
   `notes`, `affected`, `how`, `help`, `invalid`, `rejected`, `diagnostics`, `build`; 400/404/429
   otherwise. Partial edits build from the parent's stages through `rebuild.build_spec`, full
   ones without; `regenerate` plans again from the request. A fresh draw seed per request unless
   `seed` is sent. The listing entry carries `edit: {text, ops}` (not `VersionInfo`, so rebuild
   sidecars are unchanged). An edit is refused (429) while an edit or rebuild of the zone
   builds; two rebuilds still run together (step 16's tests). No `edit_outside_bands` yet: no
   quality bands exist. A `rooms_seed` rebuild of an edited version plans again from the
   request and drops purpose and lock edits (follow-up).

## Follow-ups

- A `rooms_seed` rebuild of an edited version drops its purpose and lock edits (decision 10).
- `edit_outside_bands` waits on quality bands (umbrella 19.7).
