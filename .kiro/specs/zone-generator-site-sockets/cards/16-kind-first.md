# 16 — Kind first, then the point

Index entry: `tasks.md` task 16. Requirement 3.2 (revised). `archive.md` decision 9.

## Goal
Task 11 found Sites on points drift off the stock kind mix (wilderness Normal, seeds
1000–1039, built: farmstead 13 % -> 5 %, camp 18 % -> 9 %, shrine 22 % -> 27 %; outdoor
dungeons 51 % ruins, where stock hills have none). Three causes: likes multiply the kind draw
(shrines up to 6x); a farmstead needs 100 u and fits only 44 % of points; outdoor-dungeon
points are mostly hill points that only small recipes fit.

Draw the kind first, by the biome's and Inhabitant's weights alone (as step 10 did), then
stand it on a point: the next point in the Group order whose Free radius fits that kind and
keeps clear of earlier Sites, likes choosing among fitting points of the current Group. If no
point left fits the kind, redraw the kind among those that still fit some point; drop with
`NO_POINT` only when none does. Group order, Kept_Clear, approaches and `rooms_seed` behaviour
stay as tasks 5–8 left them.

## Done when
- [ ] Kind mix, built, wilderness seeds 1000–1039 at Normal: its distance to stock plains (task
      11's sorting, sum of absolute share differences) no worse than before task 6 (master
      `4605d8d`, about 14 points); farmstead and camp shares at least before task 6's minus 3
      points. Outdoor dungeons 0–39 at Normal: no kind above 35 %. Numbers in the commit body.
      → verify: task 11's `measure11.py` / `summ11.py` (scratchpad; copy what you need)
- [ ] The plains clustering targets still hold at Normal (R pooled, share within 300 u, NN p10
      from `biomes.toml`), outdoor dungeons have a Site on 39/39 planning seeds at Normal and
      Dense, and the gate's first try stays 40/40 and 39/39.
- [ ] P4–P8 tests, goldens recaptured (hashes only), `python scripts/record_rooms.py --check`.
      → verify: `python -m pytest tests/test_site_placement.py tests/test_attach_ground.py tests/test_layout_engine.py tests/test_site_builds.py tests/test_site_decor_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Don't tune Group sizes or weights against the test; the fix is the draw order. If the kind
mix still misses because farmsteads fit too few points, stop and report the fit table rather
than widening points. Record the draw order on the stream in `_place_on_points`'s docstring.

## Result
