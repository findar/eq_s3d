# 15 — Acceptance section, thorough run, timing

Index entry: `tasks.md` task 15. Requirements 8.4, exit criteria 1–2.

## Goal
`docs/ACCEPTANCE.md` "Step 6 — Graph layouts" with pinned cases (each builds on the first attempt), a timing test, and a green thorough run.

## Done when
- [x] The acceptance section has cases for each base set, the temple layer, a big race, a graph outdoor dungeon, and the rule tooling (check, dry-run, draw), with CLI lines; every case checked to build first try.
- [x] A slow test: a 14-room graph build takes at most the classic build's time + 10 s.
      → verify: `python -m pytest tests/test_graph_layout_build.py -q`
- [x] `python -m pytest tests/ -q --hypothesis-profile thorough` is green; the frontend builds.

## Pitfalls

## Result
