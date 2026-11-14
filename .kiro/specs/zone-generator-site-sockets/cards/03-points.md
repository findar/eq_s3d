# 3 — Choosing points

Index entry: `tasks.md` task 3. Requirements 2.2–2.5. Design "How the World chooses them", "What a point holds".

## Goal
`generators/sites/points.py`: `site_points(terrain, spawn, seed, biome, rules, hill=None)` returns the point Sockets' data (id, x, y, z, Group, rank, `free` per recipe slope, `height_rank`, `clearing`, `water_d`, `zoneline_d`) in rank order, by the design's five steps, on its own stream (`_salted_seed(seed, "sites", "points")`). `hill` (a hillside Socket's footprint) puts points over the hill last, as spares. Pure; reads no Sites control, Inhabitant or room field. Nothing calls it yet.

## Done when
- [ ] P2 and P3 on generated landscapes: every point on Site-eligible ground, its `free` radii true by `disc_on_eligible`, Groups inside `gap` and `within`, Groups `spacing` apart, at least `max(2 * dense_top, 6)` points where the ground allows, the same inputs the same output.
      → verify: `python -m pytest tests/test_site_points.py -q`
- [ ] Its time on seeds 1000–1009, in the commit body (Req 2.6: 0.1 s a World).
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Reuse `sites.placement._terrain` and `vegetation.placement` (`Ground.disc_on_eligible`, `shapes_touch_quads`) rather than a second eligibility rule: placement must agree with the World about what a point offers. Salt the stream the way trees and Sites do (`_salted_seed`), so the terrain's stream never moves.

## Result
