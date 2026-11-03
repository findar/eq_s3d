# 7 — CLI, server and outdoor dungeon

Index entry: `tasks.md` task 7. Requirements 6.1, 5.3.

## Goal
`--layout` on the CLI, `layout` in the server's controls, and the outdoor dungeon's `plan_dungeon` passing it through to `layout_in_envelope`.

## Done when
- [ ] CLI and server build a grown dungeon and a grown outdoor dungeon; a bad value is a 400 / CLI error naming the allowed values.
- [ ] An outdoor dungeon with a grown layout plans on the step 5 acceptance seeds (or drops rooms with `rooms_reduced`).
      → verify: `python -m pytest tests/test_grown_layout_controls.py tests/test_outdoor_envelope.py -q`

## Pitfalls
- `plan_dungeon`'s shrink retry (step 5 task 11) must keep working; the engine is passed through, not re-chosen per scale.

## Result
