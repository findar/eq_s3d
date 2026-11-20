# 4 — Decor, map and room view read the tunnel

Index entry: `tasks.md` task 4. Requirement 4. Design "Readers".

## Goal
- Corridor RoomContexts rasterise a winding leg's floor and walls from the same `wind_leg` call
  the mesh uses, so Props stand on the tunnel's floor and against its walls.
- The map outline, the EQ map lines and the map SVG follow the tunnel.

## Done when
- [x] Every winding corridor's RoomContext floor cells lie on the strip and none lie outside it.
      → verify: `python -m pytest tests/test_winding_readers.py -q`
- [x] Decor on 5 cave builds (`EQ_PATH='F:\everquest_rof2'`) places no corridor Prop off the
      strip. Same command.
- [x] The map SVG and the EQ map `.txt` draw the winding walls. Same command, checked on one
      seed's lines.
- [ ] `python -m pytest tests/ -q -m "not slow"` is green.

## Pitfalls
- Task 3 builds the mesh in parallel. Test against `wind_leg` and the spec, not the mesh, until
  task 3 merges; the lead merges both.
- `mapgeom` unions pieces on one supporting line; check that it handles angled walls.

## Result
✔ 560ff84 · 53 passed
