# 17 — Recipes read the Scales

Index entry: `tasks.md` task 17. Requirements 13.

## Goal
A recipe's counts and chances follow the room's drawn values, not a zone-wide density.

## Done when
- [x] `by` and `from` on a recipe line, checked strictly: `python -m pytest tests/test_room_layouts.py -q`.
- [x] Temples draw low clutter and a fresh dig high, by data alone.
- [x] Task 11's bands hold under default rules: `python -m pytest tests/test_features_sweep.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Keep `plan.features` working until task 21 replaces it.

## Result
✔ a513929 · 1873 passed
