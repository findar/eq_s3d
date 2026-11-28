# 11 — Sites pack and cluster like stock

Index entry: `tasks.md` task 11. Found by task 2 (`cedb9e2`'s body has the numbers).

## Goal
Site points and Site clustering hold on any seed, not on the seeds the tests happen to use.

## Background
- Normal clustering (band 0.5-0.95) on master, lava on: 0.84 / 1.13 / 0.80 / 1.14 over four 40-seed sets, 0.975 on all 160; the test passes on its set (1000-1039) by luck. With 1-2 Sites per zone a few far-apart pairs move the mean.
- A new Group's first point is up to 192 random tries over the zone; on a nearly packed zone they miss the gaps (2 of 42 zones short with lava off, e.g. seed 1 wants 10 gets 9; seed 3 jams at 11 of 12 at any try count).
- Task 2 marked both tests `xfail(strict=False)` pointing here.

## Done when
- [ ] A Group's first point is drawn from the ground still clear of every Group (not random tries); Groups pack so `test_enough_points_for_dense_twice_over` holds on the recorded Worlds and seeds 1000-1099 (`python -m pytest tests/test_site_points.py -q -n 0`).
- [ ] Clustering measured on a pool large enough that its 40-seed swing is under the band's margin (report the swing); in band on master's bigger sizes from task 6; the xfails removed (`python -m pytest tests/test_site_bands.py -q`).
- [ ] Goldens and recordings it moves re-recorded, named in the commit body; quick tier; wilderness gate sweep.

## Pitfalls
- Don't widen the band or pick seeds to pass (the lead, step 35 task 2 review).

## Result
