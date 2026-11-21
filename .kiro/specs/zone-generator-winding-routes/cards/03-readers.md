# 3 — Decor, map and room view read the path

Index entry: `tasks.md` task 3. Requirement 4. Design "Readers".

## Goal
Corridor RoomContexts, the map line and outline, and the EQ map follow a corridor's `path`.

## Done when
- [x] Every corridor with a `path` has RoomContext floor cells only on its strip. → verify:
      `python -m pytest tests/test_wind_route_readers.py -q`
- [x] Decor on 5 cave builds (`EQ_PATH='F:\everquest_rof2'`) places no corridor Prop off the
      strip. Same command.
- [x] The map SVG and the EQ map `.txt` draw the path's walls. Same command.
- [x] `python -m pytest tests/ -q -m "not slow"` is green.

## Pitfalls
- Task 2 builds the mesh in parallel: test against `path` and the spec, not the mesh.

## Result
✔ 33fdce1 · 83 passed
