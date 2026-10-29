# 11 — Enable wilderness and close step 1

Index entry: `tasks.md` task 11. Old tasks 13.2, 14.3, 15.4. Runs in the **MAIN
checkout** after task 10 is signed off. Like task 1, this is the
single-writer integration step.

## Goal
Make wilderness an ordinary zone type that anyone can pick, and record step 1
as done.

## Done when
- [ ] Task 10 is ticked by the user. **If it isn't, stop. Don't enable on a
      green suite alone** (Requirement 13.4).
- [ ] `wilderness` is in `ENABLED_ZONE_TYPES`
      (`generators/zone_types.py`), and its entry in `ZONE_TYPE_REASONS` is
      removed. The dev flag from task 2 is deleted, along with its test, the
      clearing fixture in `tests/conftest.py`, and the `DEV_FLAGS` default in
      `web/dev.mjs`.
      → verify: `pytest tests/ -q` green. `/api/zone_types` lists wilderness as enabled.
- [ ] `docs/ACCEPTANCE.md` M1.A no longer expects wilderness to show as disabled.
- [ ] The integration note is generated, not hand-written:
      `python scripts/task_status.py zone-generator-wilderness --note 2-11`.
      Apply it to `ROADMAP.md` (Done row + "Pick up here" → roadmap step 1b,
      true-layout artifacts, the M2 spec) and the `tasks/README.md` status.
- [ ] `git push origin master`.

## Result
<!-- worker: one line -->
