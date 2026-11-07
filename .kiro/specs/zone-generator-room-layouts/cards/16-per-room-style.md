# 16 — A room's finish is its wall style

Index entry: `tasks.md` task 16. Requirements 12.

## Goal
Wall styles and looks apply per room and per corridor, drawn from finish.

## Done when
- [x] A plan naming `walls` gives the same `.eqg` bytes as master before this task, footer aside: pinned in `tests/test_room_scales.py`, proved first (F13).
- [x] `apply_walls` and `_apply_look` work per holder; each style file gains `[tune]`; `themes.toml` loses `walls`.
- [x] A zone of mixed styles passes every step 8 check over a seed sweep: `python -m pytest tests/test_walls_mixed.py -q`.
- [x] `python -m pytest tests/ -q` is green; goldens recaptured only for zones that take rules.

## Pitfalls
A corridor between different styles has no Transition yet: give it the rougher room's look until task 19. Watch build time with more materials per zone.

## Result
✔ 2e15adf · 1864 passed
