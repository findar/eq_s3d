# 5 — Sites stand on points

Index entry: `tasks.md` task 5. Requirements 3.1–3.4, 3.6, 3.7. Design "The Sites stage on points".

## Goal
`place_sites` gains a `points` argument (the World's `site` Sockets). Given points, it takes the target as now, drops points whose smallest-outer disc meets a Kept_Clear shape, draws Groups in proportion to their usable size, and at each point draws the Inhabitant, then a kind among those that fit the point (`free` at the recipe's slope, `CLEAR_WIDTH` from every earlier Site's ground and margin) by `weight * (1 + likes)`, and arranges it centred on the point as step 10 does. `_approach` refuses directions crossing an earlier Site's ground. Each `Site` gains `socket`. With no `points` it is today's placement, byte for byte (task 8 removes that path).

## Done when
- [ ] P4 on generated Worlds with points: every Site on a point, its kind fits, grounds keep `CLEAR_WIDTH`, approaches cross no other Site, no Kept_Clear point used; Sites `none` places nothing.
      → verify: `python -m pytest tests/test_site_placement.py -q`
- [ ] The kind counts over seeds 1000–1039 at Normal, today's and on points, in the commit body.
- [ ] Bytes unchanged (no caller passes points yet).
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
The target, Group order, Inhabitant and kind all draw from the one `SITES_SALT` stream, in a fixed order: write the order down in the docstring, since every Site build's bytes depend on it. Don't trust `free` near an earlier Site: test the disc against the Sites already placed. A point used is used: two Sites never share one.

## Result
