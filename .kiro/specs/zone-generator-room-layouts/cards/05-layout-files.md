# 5 — Room layouts as data

Index entry: `tasks.md` task 5. Requirements 5.

## Goal
`rules/rooms/layouts.toml` with a recipe for each room type, kinds and a default, numbers from task 1, and a strict loader. `check` covers it, `draw-rooms` draws samples, and the guide explains it. Structural prop hints leave `prop_hints`.

## Done when
- [ ] F6: every bad value named; every room type has a recipe.
      → verify: `python -m pytest tests/test_room_layouts.py -q`
- [ ] `python scripts/topology_rules.py check` prints `ok` for the file; `draw-rooms` writes a page.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Tests read `prop_hints` (the side panel, sidecar): keep the loose ones as they are.

## Result
