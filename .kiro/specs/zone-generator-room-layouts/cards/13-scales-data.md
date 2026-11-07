# 13 — Scales as data

Index entry: `tasks.md` task 13. Requirements 10.

## Goal
Weights, Layers and their multiplication, with nothing using them yet.

## Done when
- [x] `generators/room_scales.py` loads `rules/rooms/scales.toml` strictly: lists, shorthand, `override`, every bad value named.
- [x] Multiplication, override and all-zeros are pinned (F11): `python -m pytest tests/test_room_scales.py -q`.
- [x] `python scripts/topology_rules.py check` covers the file; `docs/TOPOLOGY_RULES.md` explains it.
- [x] Every race, theme and room type in the rule files has been given a thought: a missing one is fine and multiplies by nothing.

## Pitfalls
Numbers come from task 12, not taste.

## Result
✔ 231ac1b · 106 passed
