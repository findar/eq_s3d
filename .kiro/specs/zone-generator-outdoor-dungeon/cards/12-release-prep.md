# 12 — Acceptance section, thorough run, timing

Index entry: `tasks.md` task 12. Requirements 8.3, exit criteria 1–2.

## Goal
`docs/ACCEPTANCE.md` gains "Step 5 — Outdoor dungeon", a timing test proves Req 8.3, and the thorough profile is green.

## Done when
- [x] The acceptance section covers every person-judged item: the landscape, the Entrance (no gaps, carved look), walking every room from the spawn, maps, and that the in-client check is M6.
- [x] A `slow` timing test: an outdoor-dungeon build takes at most 60 s.
- [x] The fast and thorough suites pass.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Thorough runs take ~20 minutes; run them in the background.

## Result
✔ fb5d14e · 1019 passed (thorough 1018)
