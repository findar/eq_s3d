# 15 — Camps keep their tents; outdoor dungeons get Sites

Index entry: `tasks.md` task 15. Requirements 4, 7. Found at task 7 (its commit body).

## Goal
Two defects, fixed before the first look (task 9). Every camp loses all its tents ("too close" or "no room"), so a camp is a lone fire ring: make the camp's ring, sizes and Site ground hold its tents at the gate's 8 u clear width. Outdoor dungeons get no Sites at Normal, because their open ground (~0.8e6 u²) times the density rounds the target to 0: round the target so its expected value is kept (e.g. floor plus a draw on the fraction) and plains' bands still hold.

## Done when
- [ ] Over 30 seeds at Normal and Dense, every camp keeps at least 2 tents, and no recipe drops more than a fifth of its Structures.
      → verify: `python -m pytest tests/test_site_placement.py -q -k camp`
- [ ] Outdoor dungeons at Normal get Sites on some seeds; the mean target equals density x area.
      → verify: `python -m pytest tests/test_site_placement.py -q -k target`
- [ ] Gate first-try rate holds (40 wilderness + 12 outdoor-dungeon seeds, Normal and Dense), recorded in the commit body.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Sites `none` must stay step 9's bytes; the Sites stream is its own (`SITES_SALT`). Change values and placement, not the gate.

## Result
