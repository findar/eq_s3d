# 6 — Floors and ceilings move

Index entry: `tasks.md` task 6. Requirements 7.

## Goal
Vertex heights: floors rise, ceilings fall, zero in Throats, flat at Bridge slots, at the style's Relief, with the slope capped at build time.

## Done when
- [ ] W7 as properties, stacked builds included: Slab intact, headroom floor held.
- [ ] First-try gate rate unchanged on a small sweep: no retries from Relief.
      → verify: `python -m pytest tests/test_relief.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Lessons: walkable floors need deliberate shaping, the floor never sinks, and centroids across a seam must stay under the agent's step-up. Triangles must keep up-winding (task 18 of step 7) for the floor rule.

## Result
