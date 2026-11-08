# 11 — Gate sweep and stock bands

Index entry: `tasks.md` task 11. Requirements 9.1, 9.4.

## Goal
Over many seeds at Normal, built zones measure inside finding 1's bands with the survey's own code; the gate's first-try rate holds; build time within step 9's plus 5 s.

## Done when
- [ ] P9 and P10's timing.
      → verify: `python -m pytest tests/test_site_bands.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Mark the sweep slow if it is; keep a fast subset in the normal suite.

## Result

✔ d90b81c · 2082 passed