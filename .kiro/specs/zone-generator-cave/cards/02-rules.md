# 2 — Rule files: finish, recipes, topology, textures

Index entry: `tasks.md` task 2. Requirements 2.1–2.3, 2.5. Design "Rule files".

## Goal
`[themes.cave]` in `rules/rooms/scales.toml` (finish low, so rooms draw `rough`, A1); recipes for
the four new Room_Types in `rules/rooms/layouts.toml`; `cave` in `rules/topology/themes.toml`;
wall and floor texture recipes in `styles/texture_recipes.json`.

## Done when
- [ ] Over 20 `cave` dungeons (both layouts), at least 70% of rooms draw the `rough` wall style
      and none draw `built`; counts in the commit body. → verify:
      `python -m pytest tests/test_cave_rules.py -q`
- [ ] Every rule file loads and validates. → verify:
      `python -m pytest tests/test_room_scales.py tests/test_topology_ruleset.py tests/test_wall_textures.py -q`
- [ ] Look at 3 `cave` builds' maps (`generators/mapview.py`) and room views; say what you saw
      in the commit body.
- [ ] The byte check passes; `python -m pytest tests/ -q` is green.

## Pitfalls
Lessons-learned "Walkable floors" and the walkability tests: a `rough` room's floor relief must
not dig pits. `warren` as base set: check its kinds cover the Room_Types (design "Rule files").

## Result
