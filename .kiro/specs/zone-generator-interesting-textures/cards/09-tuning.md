# 9 — Tune from the first look

Index entry: `tasks.md` task 9. Depends on task 8's findings.

## Goal
Apply task 8's findings to the recipes and painters without breaking Y4–Y5.

## Done when
- [x] Each finding is addressed or answered in the commit body.
- [x] `python -m pytest tests/ -q` is green.
      → verify: `python -m pytest tests/ -q`.

## Pitfalls
- Prefer recipe data over painter code. Never loosen a property to fit a
  tuning.
- If task 8 signed off with no findings, record that and tick this task.

## Result
✔ f07cf6d · 839 passed
