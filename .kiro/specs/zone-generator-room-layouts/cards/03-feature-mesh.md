# 3 — Feature meshes

Index entry: `tasks.md` task 3. Requirements 3.

## Goal
Closed solids for `pillar`, `plinth`, `boulder` and `dais`, with each style's form, standing on any floor and meeting any ceiling (step 8's relief). Dais with steps or a low rise. Driven by tests, with no layout placing one yet.

## Done when
- [ ] F2 and F3 as properties, over relief and styles.
- [ ] The room's closure check passes with Features in it; a Dais walks from the floor; median edge in the era band; polygon cap set from a measure.
      → verify: `python -m pytest tests/test_feature_mesh.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Winding: floors up (step 7 task 18). Share a Dais top's vertices, or the gate pays for every seam. Texture U runs on round a solid, as walls do. No per-vertex Python noise.

## Result
