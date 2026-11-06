# 10 — Textures follow the style

Index entry: `tasks.md` task 10. Requirements 9.

## Goal
A style's `look` reaches the materials: `rough` and `hewn` walls take rock in place of coursed masonry, with step 4's texel density and Look_Stats bands holding, and a theme's character kept where it has one.

## Done when
- [x] Each style's walls name the right family; bands hold.
      → verify: `python -m pytest tests/test_wall_textures.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Step 4's bands are per theme: a rough fortress is a combination the bands weren't measured on, so say what's checked. Texture names stay readable (step 3).

## Result
✔ 9931382 · 1600 passed
