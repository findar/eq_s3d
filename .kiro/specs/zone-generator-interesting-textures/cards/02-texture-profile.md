# 2 — Texture_Profile in the style profiles

Index entry: `tasks.md` task 2. Design: "Texture_Profile". Requirement 2.

## Goal
Each theme's style profile gains a measured `textures` block (texel density per
surface, Look_Stats bands) in place of the placeholder `uv.scale`.

## Done when
- [x] The analyzer writes the block for dungeon, city, outdoor and cave from
      their analysed zones, and `uv.scale` is gone.
- [x] Y2: running it twice gives byte-identical blocks.
- [x] The dungeon profile's wall p50 is within the design's research range
      (12–24 u) and its Look_Stats p50s within 20 % of the research table.
      → verify: `python -m pytest tests/test_texture_profile.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Skip `palette.bmp` and non-256×256 images.
- Other code may read `uv.scale`; grep before removing it, and ask if a caller
  outside `Owns` needs changing.

## Result
✔ 85a8519 · 792 passed
