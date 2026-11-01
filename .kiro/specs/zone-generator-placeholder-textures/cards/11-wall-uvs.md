# 11 — Wall UVs follow EQ's convention

Index entry: `tasks.md` task 11. Found in task 4 (commit `448cd04`). Req 6.1
and exit criterion 3 (text reads the right way up).

## Goal
Box-backend walls carry UVs the way stock zones do, so a placeholder label on
a wall reads upright and unmirrored from where a player stands: `v` grows
down the wall (the texture's top row at the top of the wall), and `u` grows to
the right as seen from inside the room or corridor.

Task 4's probe: stock walls run `v` down as `z` rises on 88–98 % of wall
edges (Dranik catacombs and sewers, Anguish); ours run it up on every wall
edge, and our `u` runs right-to-left on half the walls.

## Done when
- [x] First commit: X3's golden hash leaves out UVs (positions, normals,
      colours and each polygon's v1/v2/v3/flags/material only), re-recorded
      on unchanged code, and still passes.
- [x] After the fix the same X3 goldens pass untouched: only UVs moved.
- [x] For dungeon (flat and elevated) and city builds, on every wall
      triangle `v` falls as `z` rises, and `u` rises to the right as seen from
      the room's or corridor's inside; the texel scale (100 u per repeat) is
      unchanged.
      → verify: `python -m pytest tests/test_wall_uvs.py tests/test_material_names.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Decide "inside" from the room's or corridor's footprint (which side its
  centre line is on), not from triangle winding: our walls' winding doesn't
  say which side a player sees.
- Floors and ceilings are out of scope; leave their UVs alone.
- Wilderness terrain UVs are out of scope.
- `analyzer.traverse` and the outline code read positions, not UVs, so
  nothing else should move; if a test outside `Owns` breaks, stop and ask.

## Result
✔ 277b5d3 · 737 passed
