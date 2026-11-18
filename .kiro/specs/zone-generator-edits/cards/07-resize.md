# 7 — Resize ops

Index entry: `tasks.md` task 7. Requirement 2.7. Design "Resize". Decision 6 (`archive.md`).

Owns: generators/resize.py, generators/edits.py (the resize rows only), tests/test_resize.py

## Goal
`widen_room`, `narrow_room`, `taller_room` and `lower_room` change the saved spec (`how: full`).
Add `resize_room(doc, room, op, by) -> (doc', applied, affected, notes)` in `generators/resize.py`
and wire `apply_edits` to it. No floor moves: elevation is never relaxed. The steps:
1. Scale the room's box about its centre: width and depth for widen and narrow, height for
   taller and lower.
2. Each corridor that touches the room has its end on that room moved out or in by the wall's
   shift. The end's position along the wall stays. Its other end isn't touched.
3. Re-dress the room: `apply_walls`, or `apply_walls_by_finish` when `layout.walls` is `rules`,
   then `apply_features`. Both run at `rooms_seed or seed` with `layout.features`. Keep each
   corridor's saved Transition look (floor, wall and ceiling materials, `rough`, `material`)
   where the form is the same. Without that, re-dressing an unchanged spec moves a frame's
   materials (graph16 seed 2, corr_13).
4. Clamp by bisection to the largest size, between 1 and the size asked for, that passes all of
   these: no 3D overlap that wasn't there before, between the room or its corridors and anything
   else; each door at least half a corridor and 1 u inside its wall; each touching corridor's route kind, axes and leg
   directions unchanged; its ramp grade at most max(0.5, the old grade); a stair's
   `stair_layout` and a Bridge's `bridge_layout` still there, with `cramped` unchanged; and the
   room at least as tall as each touching corridor at its door. Nothing fits: rejected, with a
   note. The notes give the size asked for and the size applied (19.4).
5. Affected_Set: the room and the corridors that touch it, plus every room whose
   `geometry._door_openings` or `_bridge_slots` changed and every corridor whose `bridge_layout`
   or `stair_layout` changed. Work these out from the spec, before any build.

Task 2's measurements: graph16 seed 2, graph12 dramatic seed 7, tomb seed 4 and classic8 seed 3,
every room, ops at ×1.25, ×0.75, ×1.3 and ×0.7. That is 164 trials. Widen was refused twice, by
grade (dramatic s7 corr_3). Of the other 162, 130 changed only the room and its corridors. The
rest, 32, also changed 42 neighbouring elements, and step 5 predicted all of them: ramp lintels at
a neighbour's door (18), the slot under a moved Bridge (14), and a Bridge over the room itself
(10, which covers every neighbour change from taller and lower). Lower
stops at about ×0.71, where the room is no taller than its corridors. The full gate passed 11
resized builds.

## Done when
- [ ] For each of those 4 specs, every room and op: the triangles of every room and corridor
      outside the Affected_Set are unchanged (sorted per element, compared by material name). Per
      element means splitting the polygons at each `MeshBuilder.add_room`/`add_corridor` call of
      the builder's `_build_geometry`. → `python -m pytest tests/test_resize.py -q -n0`
- [ ] A clamped resize notes the size asked for and the size applied; a refused one (dramatic s7
      room_1 widen) is `applied: false` with its reason; the input doc is unchanged.
      → the same command
- [ ] A resized build of each zone type passes `generate_validated`'s gate (pinned, one attempt).
      → the same command (mark it `slow` if it's over a few seconds)
- [ ] Bytes unchanged (`tasks.md` "Bytes"), and the full suite passes. → `python -m pytest tests/ -q`

## Pitfalls
Re-dressing isn't idempotent until the Transition look is kept (step 3). `stair_layout` avoids
every room's footprint, so check it for every stair, not only the touching ones. Decor, lights,
regions, gate lock points and POIs weren't measured in task 2. They follow the room in a full
rebuild, so confirm them in the viewer at the first look. Lessons-learned "Bound elevation by
the corridor run" and "Same-axis room pairs need a Z-route".

## Result
