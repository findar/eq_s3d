# 3 — Structure models

Index entry: `tasks.md` task 3. Requirements 3.1–3.3, 3.5.

## Goal
Generated low-poly models for hut, tent, lean-to, tower, fire ring, fence run, standing stone and ruin wall, at finding 1's triangle counts: solid parts closed, passable parts flagged, origin at ground, a buried skirt, Enterable openings at least clear width and head height, the ground as an Enterable floor. Variants per Inhabitant where the shape differs.

## Done when
- [ ] P3: every model closed where solid, round-trips through the `.mod` writer exactly, openings measured.
      → verify: `python -m pytest tests/test_site_models.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Follow `generators/vegetation/models.py`: float32-rounded coordinates, no mesh file read (umbrella Req 32.7).

## Result
✔ 8998ba0 · 2040 passed
