# 1 — The cave Purpose

Index entry: `tasks.md` task 1. Requirement 1. Design "Room_Types".

## Goal
`cave` in `semantics.ARCHETYPES` and `VALID_DUNGEON_THEMES`: the Room_Types `cave_mouth`,
`cavern`, `crystal_grotto`, `grotto`; entrance / hub / climax / arc; `_THEME_KIND_TYPES` for the
graph layout; a palette in `_THEME_PALETTES` and a cool, low light mood with a brighter crystal
climax.

## Done when
- [x] A dungeon spec labelled with Purpose `cave` (both layouts, 8–30 rooms) has a `cave_mouth`
      entrance, a `crystal_grotto` climax, only `cave` Room_Types, a `water` region on every
      `flooded_gallery`, and lights colder and dimmer on average than `fortress`'s.
      → verify: `python -m pytest tests/test_cave_purpose.py -q`
- [x] `kind_types("cave")` maps every kind and `unmapped_kinds` is empty. Same command.
- [x] The rule validators load with `cave` in the vocabulary and no entry for it yet (tasks 2–3
      fill them). → verify:
      `python -m pytest tests/test_decor_rules.py tests/test_room_scales.py tests/test_topology_ruleset.py -q`
- [ ] The byte check in `tasks.md` passes; `python -m pytest tests/ -q` is green.

## Pitfalls
Districts draw from `sorted(ARCHETYPES)`: adding `cave` changes drawn-Purpose districted zones
for a seed (A4, allowed); a test pinning one such seed's Purposes is updated, not loosened, and
named in the commit body. Don't reorder existing `ROOM_TYPES`/`ARCHETYPES` entries.

## Result
✔ b526dd8 · 3732 passed, 4 expected failures (2 → task 2, 1 → task 5, 1 → new recording task)
