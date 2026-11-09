# 7 — Decor recipes as data

Index entry: `tasks.md` task 7. Requirements 5, 7.

## Goal
`rules/decor/rooms.toml` (Decor_Recipes by default, kind and room type, asking for Props by Tag; Dressing by POI purpose) and `sets.toml` (which race, theme and zone type take which Sets), with a strict loader and Weights by Layer. `topology_rules.py check rules/decor` and `draw-decor`.

## Done when
- [ ] P7: every bad value is named by file, entry and field; every Tag a recipe asks for has a usable model or the line is named; every room type in `rules/rooms/layouts.toml` has a recipe or falls back.
      → verify: `python -m pytest tests/test_decor_rules.py -q`
- [ ] `python scripts/topology_rules.py check rules/decor` passes.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Follow `generators/sites/rules.py` and step 9's Layer arithmetic (`generators/room_scales.py`). Until task 4's review lands, test against fixture tags; the real check runs after it.

## Result
✔ 192400c · 2229 passed

