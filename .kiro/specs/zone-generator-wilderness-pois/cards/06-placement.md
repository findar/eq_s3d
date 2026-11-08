# 6 — Site placement

Index entry: `tasks.md` task 6. Requirements 4, 6.

## Goal
Choose Site centres on eligible ground (playable plains, slope within the recipe, outside Kept_Clear, spaced), scored by the recipe's likes; arrange each recipe's Structures; keep each Site_Clear free; drop and record misfits; name POIs on reached ground. Its own salted stream. Trees keep off Site ground.

## Done when
- [ ] P4 and P7 on generated landscapes.
      → verify: `python -m pytest tests/test_site_placement.py -q`
- [ ] P5: terrain identical across densities, trees byte-identical with Sites `none`.
      → verify: `python -m pytest tests/test_site_placement.py -q -k identical`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Salt the seed the way trees do (`_salted_seed`), so the terrain's stream never moves (trees spec Decision 4).

## Result
✔ 3bfa78b · 1998 passed
