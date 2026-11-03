# 6 — Plan field, planner words, sidecar

Index entry: `tasks.md` task 6. Requirements 6.2, 6.3. Design "Selection and the sidecar". Needs Open questions 1–3 answered.

## Goal
The `layout` option on `ZonePlan` (as Open question 1 settles), the planner's topology words (Open question 2), `expand` passing it to the layout, and the sidecar's `layout` block.

## Done when
- [ ] A plan without the field loads as `classic`; an unknown value is an error naming the allowed values (umbrella Req 22.8).
- [ ] The planner words of umbrella Req 22.5–22.7 pick the profile (as answered).
- [ ] The sidecar has a `layout` block for classic and grown builds; classic Zone_Spec JSON is unchanged (task 2 goldens pass).
      → verify: `python -m pytest tests/test_grown_layout_plan.py tests/test_layout_engine.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- `ZoneSpec.layout` is `None` for classic and left out of the JSON when `None` (design).
- Only the zone types Open question 3 lists take a grown layout; others ignore the field.

## Result
