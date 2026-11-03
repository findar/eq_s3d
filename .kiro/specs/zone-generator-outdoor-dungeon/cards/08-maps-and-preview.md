# 8 — Maps and preview

Index entry: `tasks.md` task 8. Requirements 7.2, 7.3.

## Goal
The outline and EQ map files show the open ground and the dungeon, the dungeon on its own depth band where it lies under the ground; the preview shows both.

## Done when
- [x] Outline and map files are produced for a sample of seeds; the dungeon's walls appear on a separate band from the open ground where it is under it.
      → verify: `python -m pytest tests/test_outdoor_dungeon_maps.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- M2's depth bands already handle stacked floors; check before changing them.

## Result
✔ 9b003b0 · 1004 passed
