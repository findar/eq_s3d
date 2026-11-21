# 2 — Measure the range

Index entry: `tasks.md` task 2. Requirement 2. Design "Range".

## Goal
Pick `WINDING_MAX` from measurement, and decide whether the cave run factor follows `winding`
above 1.

## Done when
- [x] For k in {0, 0.5, 1, 1.5, 2, 3}, over 40 cave graph builds (seeds 1000–1039) and 20 warren
      graph builds (seeds 1000–1019), 8–30 rooms, each verticality, `EQ_PATH` set: wind share,
      path share, median and p90 largest stray, door-to-door median and gate passes, as a table in
      the commit body and `archive.md` "Decisions".
- [x] `WINDING_MAX` set to the largest k whose stray still rises and whose gate holds; any run
      factor coupling (k > 1 only) recorded with its numbers.
- [x] `python -m pytest tests/test_winding_control.py tests/test_cave_profile.py -q` green, and the
      byte check passes (k = 1 untouched).

## Pitfalls
- Sweep with `EQ_PATH='F:\everquest_rof2'` set, or decor results aren't comparable.
- Use `--jobs` ≤ 4 and check no other pytest or sweep is running first.

## Result
✔ 90278e9 · 3133 passed (not slow), byte check 106 passed
