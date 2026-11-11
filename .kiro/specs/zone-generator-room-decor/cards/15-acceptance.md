# 15 — Acceptance section, thorough run

Index entry: `tasks.md` task 15.

## Goal
A "Step 11 — Decorating rooms" section in `docs/ACCEPTANCE.md`: pinned cases (seeds and controls) for room types, races and themes, cities, outdoor dungeons, Sites, Decor densities and a decor reroll, with checks; a thorough run; the frontend builds.

## Done when
- [ ] Every pinned case builds first try and shows what its row says.
- [ ] The thorough suite is green.
      → verify: `python -m pytest tests/ -q --hypothesis-profile thorough`

## Pitfalls
Recheck every case on the final code before landing. Pre-existing thorough failures (step 10 archive) are named, not hidden.

## Result
✔ 802fbaf · 2371 passed, 1 failed (thorough): `test_properties_mapgeom.py::test_reachable_only`, pre-existing (replays at 3ae15d5^)
