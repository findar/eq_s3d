# 12 — Acceptance section, thorough run, timing

Index entry: `tasks.md` task 12. Requirements 7.4, exit criteria 1–2.

## Goal
`docs/ACCEPTANCE.md` "Step 6 — Grown layouts" with pinned cases (each builds on the first attempt), a timing test, and a green thorough run.

## Done when
- [ ] The acceptance section has cases for each profile, a themed grown dungeon, a grown outdoor dungeon and a prompt with topology words, with CLI lines; every case checked to build first try.
- [ ] A slow test: a 14-room grown build takes at most the classic build's time + 10 s.
      → verify: `python -m pytest tests/test_grown_layout_build.py -q`
- [ ] `python -m pytest tests/ -q --hypothesis-profile thorough` is green; the frontend builds.

## Pitfalls

## Result
