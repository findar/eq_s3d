# 3 — Outlines and their meshes

Index entry: `tasks.md` task 3. Requirements 2, 4.

## Goal
`generators/outline.py`: Voronoi and grid Cell_Complexes, Throats, Core, growth with shapes, Fill. `MeshBuilder.add_outline_room`: floor and ceiling fans, vertical walls on shared vertices, doors and lintels, flat for now (Relief is task 6). Driven by tests, with no layout producing one yet. Sets the polygon cap from a measured margin.

## Done when
- [ ] W1 and W2 as Hypothesis properties over rooms, door sets and sizes.
- [ ] W5 and W6 on built meshes: closed apart from doors, doors flush with corridors, walk gate passes.
- [ ] Median edge in the era band; texture U continuous round a wall run (W9).
      → verify: `python -m pytest tests/test_outline.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Mirrored seeds make Voronoi edges follow a Throat; check for degenerate cells at Box corners and with Throats near each other. Own rng stream per room. No `shapely`. Lessons: never a per-vertex Python loop in noise.

## Result
