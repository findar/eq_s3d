# 22 — Lights laid out as a set; one-per-room kinds

Index entry: `tasks.md` task 22. Added from the user's acceptance pass (task 16), 2026-11-12:
"torches should be at a common height. some objects like light sources generally have
symetrical layouts, so either evenly spaced or on directly opposite walls. for other objects
like a forge i would usually only expect a single one in a room".

## Goal
1. **One height:** a room's wall lights share one mount height over its floor (from stock).
2. **Symmetry:** a room's lights are placed as a set: evenly spaced along the walls, or in
   pairs on directly opposite walls (corner lights in opposite or all corners), not scattered.
   A spot the set needs that isn't free drops the set to a smaller symmetric one, never to a
   lopsided one.
3. **One per room:** kinds stock rooms hold at most once (forge, and whatever else the stock
   survey shows: measure it, don't guess) are placed at most once a room.

## Done when
- [ ] Measured on stock first (wall-light heights, how stock spaces lights, which kinds stock
      holds once a room); the figures go in the commit body.
- [ ] A test per goal fails on the old code and passes now.
      → verify: `python -m pytest tests/test_decor_placement.py tests/test_decor_builds.py -q`
- [ ] Bands and first try still hold, Normal and Dense.
      → verify: `python -m pytest tests/test_decor_bands.py -q -n 0`
- [ ] The step 11 ACCEPTANCE section checks these three.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Placement must still agree with the gate (decisions 31, 47, 48). Don't fix symmetry by placing
fewer lights than the bands need.

## Result
✔ d69bb1f · 2383 passed
