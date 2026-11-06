# 13 — Acceptance section, thorough run, timing

Index entry: `tasks.md` task 13. Requirements 9.4, exit criteria 1–2.

## Goal
`docs/ACCEPTANCE.md` "Step 7 — Dungeon verticality" with pinned cases made from the Controls panel alone (each builds on the first attempt), a timing test, and a green thorough run.

## Done when
- [x] Cases: both rule sets at moderate and dramatic, flat (one level), a temple, a big race, an outdoor dungeon at dramatic, and bridges if they landed; every case verified first try through the server route, its sidecar showing what the doc says.
- [x] A slow test: a 14-room multi-level build takes at most step 6's graph build time + 10 s.
      → verify: `python -m pytest tests/test_vertical_build.py -q`
- [x] `python -m pytest tests/ -q --hypothesis-profile thorough` is green; the frontend builds.

## Pitfalls
- Never the description box for a case (step 6 first look): it doesn't take the controls.

## Result
✔ 88ea3ef · 1430 passed (thorough)
