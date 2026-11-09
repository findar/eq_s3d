# 14 — Gate sweep and stock bands

Index entry: `tasks.md` task 14. Requirements 12.1, 12.4.

## Goal
Over many seeds at Normal, built rooms inside the survey's bands for Props per room, Category shares and Mount shares, measured with the survey's own code; gate first-try rate; build time within step 10 + 5 s.

## Done when
- [ ] P12.
      → verify: `python -m pytest tests/test_decor_bands.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Import the survey's measures; don't re-implement them. Timing tests fail under parallel load: rerun alone.

## Result

