# 11 — Tune from the first look

Index entry: `tasks.md` task 11. Depends on task 10's findings.

## Goal
Apply task 10's findings to the kit data and, where needed, the model or
placement code, without breaking T1–T9.

## Done when
- [ ] Each finding is addressed or answered in the commit body.
- [ ] `python -m pytest tests/ -q` is green.
      → verify: `python -m pytest tests/ -q`.

## Pitfalls
- Prefer kit data over code. Never loosen a property to fit a tuning.
- If task 10 signed off with no findings, record that and tick this task.

## Result
