# 2 — The gate learns Structures

Index entry: `tasks.md` task 2. Requirements 2.

## Goal
Before any generator places one, the gate judges hand-built zones holding Structures, from the models' own collidable triangles placed by their ZON objects: a Footprint cutting reached ground, an opening narrower than the clear width or lower than head height, an unreached interior, an unreached POI. The Footprint check replaces `trees_block` and agrees with it on every tree-only zone.

## Done when
- [ ] P1: a hand-built case of each failure fails, named, pinned as an example.
      → verify: `python -m pytest tests/test_gate_footprints.py -q`
- [ ] P2: on tree-only builds the Footprint check gives `trees_block`'s answer.
      → verify: `python -m pytest tests/test_gate_footprints.py -q -k trees`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Judge from the models, not the generator's record, so the gate doesn't trust the placer. Thin walls must not slip between raster samples (design Risks). Watch the cost: step 8's gate work once took builds from 1 s to 18 s.

## Result
✔ 9f9ff29 · 1971 passed
