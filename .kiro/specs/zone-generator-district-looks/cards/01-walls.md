# 1 — Walls per District

Index entry: `tasks.md` task 1. Requirement 1. Design "Task 1".

## Goal
Each room of a multi-District dungeon draws its Scales, and so its wall style, from its own
District's Purpose (`room.room_theme`), not from the zone's `dungeon_theme`.

## Done when
- [x] Graph layout, 16 rooms, 5 seeds each for pinned Purposes `cave` then `fortress`, and
      `fortress` then `cave`:
      - the cave District's rooms outside a masonry wing are at least 70% `rough`;
      - the fortress District's rooms outside a cave wing have no `rough`;
      - the counts, and the wing rooms separately, are in the commit body.

      (amended by the lead: wings keep their override; the lean stops at a District edge)

      → verify: `python -m pytest tests/test_district_looks.py -q`
- [x] The byte check in `tasks.md` passes. A moved golden is named in the commit body (A4).
- [ ] `python -m pytest tests/ -q -m "not slow"` is green.

## Pitfalls
- Rooms lean toward their neighbours only within a wing and (amended) a District. Note what a
  Threshold's two sides look like in the commit body.
- Set Districts and pinned Purposes through the plan (`districts`, `district_plan`), as
  `tests/test_district_purposes.py` does.

## Result
✔ d87dabf · 4 passed
