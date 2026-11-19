# 2 — Purposes, palettes and lights

Index entry: `tasks.md` task 2. Requirement 2. Design "Purposes".

## Goal
The compatibility table and `assign_district_purposes(part, purpose, proposals, relationship,
rng) -> (list[DistrictSpec-ish], notes)`; `label_rooms(..., districts=...)` labelling each room
from its District's Purpose by in-District depth; `realize_semantics` choosing palette and light
by `room_theme`, with the `abandoned` variant and the Threshold rule (23.5); palettes for
`war_city`, `warren`, `corrupted_sanctum`, `mine_delve`, used only in multi-District zones.

## Done when
- [x] `sequential` gives pairwise-distinct, consecutively compatible Purposes; `factional`
      pairwise-distinct contrasting ones; `abandoned_vs_active` one Purpose with the variant on
      every non-entrance District; proposals fill the first k; unknown values fall back with a
      note naming them; a pinned Purpose gives every District it. → verify:
      `python -m pytest tests/test_district_purposes.py -q`
- [x] On a hand-built two-District spec (all 11 Purposes, and a pinned single Purpose), the two
      Threshold ends differ in material set and in light colour or intensity. Same command.
- [x] `label_rooms` / `realize_semantics` with `districts=None` are unchanged: the byte check in
      `tasks.md` passes; `python -m pytest tests/ -q` is green.

## Pitfalls
Lights are matched to rooms by position in `_set_room_light`; keep that. New Material_Names must
be distinct per variant (the texture is keyed on the name). Don't touch the single-District path's
rng draws.

## Result
✔ de2e44e · 3635 passed
