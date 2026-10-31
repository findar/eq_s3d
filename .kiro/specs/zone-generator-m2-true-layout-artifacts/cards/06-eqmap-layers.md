# 6 — EQ map layers from the outline

Index entry: `tasks.md` task 6. Design: "EQ map writer and parser" (Build,
Layer order). Requirements 5.1, 5.3–5.7.

## Goal
Add `build_map_file(outline, spec, name)` to `generators/eqmap.py`: one layer
per depth band, one line record per outline segment in that band's colour, and
`Entrance` / `Boss` labels in the right band.

## Done when
- [x] Property 12 (the map files mirror the outline: one line per consecutive
      point pair, none degenerate, band colours, layer file order) holds on
      100 synthetic outlines and, marked `slow`, on 10 builds.
- [x] Property 13 (every line endpoint and label lies within the walkable floor's
      XY box + 0.5 u and in the allowed Z range; labels sit inside their room)
      holds on 15 builds, `slow`.
      → verify: `python -m pytest tests/test_eqmap.py -q`.
- [x] Exactly one `Entrance` label and one `Boss` label per climax room, all
      size 2, and no other labels.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- The text is always `Boss` until M3 adds a name field (`archive.md`).
- Identical input must give identical bytes: normalise `-0` (Decision 5).

## Result
✔ ec02d56 · 568 passed
