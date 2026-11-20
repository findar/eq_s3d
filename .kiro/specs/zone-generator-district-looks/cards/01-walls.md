# 1 — Walls per District

Index entry: `tasks.md` task 1. Requirement 1. Design "Task 1".

## Goal
Each room of a multi-District dungeon draws its Scales, and so its wall style, from its own
District's Purpose (`room.room_theme`), not from the zone's `dungeon_theme`.

## Done when
- [ ] Graph layout, 16 rooms, 5 seeds each for pinned Purposes `cave` then `fortress`, and
      `fortress` then `cave`:
      - the cave District's rooms are at least 70% `rough`;
      - the fortress District's rooms have no `rough`;
      - the counts are in the commit body.

      → verify: `python -m pytest tests/test_district_looks.py -q`
- [ ] The byte check in `tasks.md` passes. A moved golden is named in the commit body (A4).
- [ ] `python -m pytest tests/ -q -m "not slow"` is green.

## Pitfalls
- Rooms lean toward their neighbours only within a wing. Don't change the lean; note what a
  Threshold's two sides look like in the commit body.
- Set Districts and pinned Purposes through the plan (`districts`, `district_plan`), as
  `tests/test_district_purposes.py` does.

## Result
