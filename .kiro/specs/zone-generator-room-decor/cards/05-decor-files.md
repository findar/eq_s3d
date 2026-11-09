# 5 — Decor recipes as data

Index entry: `tasks.md` task 5. Requirements 6.

## Goal
`rules/decor/` (props, rooms, sets) and its strict loader: Prop_Kinds, Decor_Recipes by default, kind and room type, Dressing by POI purpose, Material_Sets by race and theme, Weights by Layer. Placeholder sizes until task 3. `topology_rules.py check rules/decor` and `draw-decor`.

## Done when
- [ ] P6: every bad value is named by file, entry and field; every kind and set referenced exists; every room type in `rules/rooms/layouts.toml` has a recipe or falls back.
      → verify: `python -m pytest tests/test_decor_rules.py -q`
- [ ] `python scripts/topology_rules.py check rules/decor` passes.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Follow `generators/sites/rules.py` and step 9's Layer arithmetic (`generators/room_scales.py`).

## Result

