# 10 — Record cave rooms for the room-context corpus

Index entry: `tasks.md` task 10. Added by the lead at the task 1 merge: task 1's suite showed
`test_room_context.py::test_the_corpus_covers_every_room_type_wall_style_and_race` needs a
recorded room for each new Room_Type, and no task owned it.

## Goal
A `cave` entry in `RECORDINGS` (`scripts/record_rooms.py`) whose recording covers `cave_mouth`,
`cavern`, `crystal_grotto` and `grotto`, and its fixture in `tests/fixtures/rooms/`, recorded
after tasks 2-4 so it holds the cave's real recipes, decor and scale.

## Done when
- [x] → verify: `python -m pytest tests/test_room_context.py -q`
- [x] Existing fixtures unchanged (`git diff --stat` shows only the new fixture and the script).
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Fixtures hold measured geometry, never client art. Recording needs `EQ_PATH`.

## Result
✔ d869ca4 · 3769 passed, 1 failed (task 5's three_districts) · seed 125
