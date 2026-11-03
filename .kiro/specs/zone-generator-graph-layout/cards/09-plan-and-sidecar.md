# 9 — Plan fields, theme kind map, sidecar

Index entry: `tasks.md` task 9. Requirements 7.2–7.5. Design "Selection and the sidecar".

## Goal
`ZonePlan.layout` and `ZonePlan.rule_set`, `expand` passing them to the layout with the theme map, each theme's kind → room type map in `semantics`, and the sidecar's `layout` block.

## Done when
- [ ] A plan without the fields loads as classic; an unknown value is an error naming the allowed values.
- [ ] With `graph`, the set comes from the theme (layers included) unless `rule_set` names one; each theme maps every shipped kind to a room type (a fortress's `deep` is its throne room).
- [ ] The sidecar has a `layout` block for classic and graph builds; classic Zone_Spec JSON is unchanged (task 2 goldens pass).
      → verify: `python -m pytest tests/test_graph_layout_plan.py tests/test_layout_engine.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- `ZoneSpec.layout` is `None` for classic and left out of the JSON when `None` (design).
- Only `dungeon` and `outdoor_dungeon` take the toggle; other types ignore it.

## Result
