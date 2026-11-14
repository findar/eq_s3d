# 4 — The World offers point Sockets

Index entry: `tasks.md` task 4. Requirements 1, 2.1, 2.5, 2.6. Design "Point Sockets", "Hand-offs".

## Goal
`world.KINDS` gains `site`; `world.VERSION` becomes 2 (a version 1 file refused, named). `world_for` adds a wilderness's and an outdoor dungeon's point Sockets (`site0`…, after `ground`) from `points.site_points` on the World's own seed, biome and terrain; on an outdoor dungeon it passes the hillside Socket's footprint. The World corpus is re-recorded (every file: the version changes) and covers Groups of two or more and an outdoor dungeon's points over its hill. No build reads the points yet: bytes unchanged.

## Done when
- [ ] P1: a v2 World with `site` Sockets round-trips exactly; a v1 file is refused, naming the file and both versions; `world_for` reads no Site control (patched to raise).
      → verify: `python -m pytest tests/test_world.py -q`
- [ ] The corpus re-makes the same, covers the cases above and stays small.
      → verify: `python scripts/record_worlds.py --check` and `python -m pytest tests/test_world_corpus.py -q`
- [ ] Points add at most 0.1 s to a World (median, seeds 1-5), in the commit body.
      → verify: `python scripts/stage_timings.py --seeds 1-5`
- [ ] Bytes unchanged.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Keep `world.py` free of top-level imports from the generators (step 12 task 2): import `points` inside `world_for`. `stages.sockets_sidecar` and `stages.ORDER` meet a `site` Socket from now on: if either fails on one, the fix belongs to task 6's file, so stop and say so rather than widening Owns. Re-record the corpus in the same commit as the version change.

## Result
