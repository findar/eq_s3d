# 10 — CLI, server and outdoor dungeon

Index entry: `tasks.md` task 10. Requirements 7.1, 6.6.

## Goal
`--layout` and `--rule-set` on the CLI, the same in the server's controls, and the outdoor dungeon's `plan_dungeon` passing them through to `layout_in_envelope`.

## Done when
- [x] CLI and server build a graph dungeon (each set) and a graph outdoor dungeon; a bad value is a 400 / CLI error naming the allowed values.
- [ ] A graph outdoor dungeon plans on the step 5 acceptance seeds (or drops rooms with `rooms_reduced`).
      → verify: `python -m pytest tests/test_graph_layout_controls.py tests/test_outdoor_envelope.py -q`

## Pitfalls
- `plan_dungeon`'s shrink retry (step 5 task 11) must keep working; the engine is passed through, not re-chosen per scale.
- An unknown `layout` or `rule_set` raises `ValueError` from `ai/schema.py` (task 9), which the server returns as a 500 today: make it a 400 naming the allowed values.

## Result
