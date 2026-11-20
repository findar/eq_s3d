# 4 — Cave ceilings

Index entry: `tasks.md` task 4. Requirement 4. Design "Task 4".

## Goal
The cave profile's Size shift shrinks footprints only. Room and corridor heights stay as they are
for the same seed with no profile. (Step 21 follow-up: ceilings dropped about 12%.)

## Done when
- [x] A `cave` dungeon on both layouts, 10 seeds, built with and without the profile:
      - footprints are still smaller, within step 21's 7.6% (classic) and 13.9% (graph);
      - mean room height is within 2% of the no-profile build;
      - the numbers are in the commit body.

      → verify: `python -m pytest tests/test_cave_profile.py -q`
- [x] The byte check passes, and `python -m pytest tests/ -q -m "not slow"` is green.

## Pitfalls
- `generators/layout.py` is a hotspot: touch only the profile shift.
- Heights feed stairs and Levels (`step_rise_min/max`), so also run `tests/test_cave_purpose.py`
  and the walkability tests.

## Result
✔ 37c151e · 26 passed
