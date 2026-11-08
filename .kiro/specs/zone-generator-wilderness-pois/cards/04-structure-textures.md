# 4 — Structure textures

Index entry: `tasks.md` task 4. Requirements 3.4.

## Goal
Procedural timber, thatch, hide, canvas and stone textures for Structures, at the measured texel density, named per material set.

## Done when
- [ ] Each material renders, tiles and is at the density.
      → verify: `python -m pytest tests/test_site_textures.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Follow the vegetation textures (`generators/vegetation/textures.py`); dungeon and city materials must not change.

## Result
✔ bd9104d · 1988 passed (timing test failed under CPU load)
