# 17 — Recipes read the Scales

Index entry: `tasks.md` task 17. Requirements 13.

## Goal
A recipe's counts and chances follow the room's drawn values, not a zone-wide density.

## Done when
- [ ] `by` and `from` on a recipe line, checked strictly: `python -m pytest tests/test_room_layouts.py -q`.
- [ ] Temples draw low clutter and a fresh dig high, by data alone.
- [ ] Task 11's bands hold under default rules: `python -m pytest tests/test_features_sweep.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Keep `plan.features` working until task 21 replaces it.

## Result
