# 7 — Acceptance section, thorough run

Index entry: `tasks.md` task 7.

## Goal
`docs/ACCEPTANCE.md` gains "Step 16 — Partial rebuild": pinned cases (the 16-room Graph dungeon
seed 2, a city, an outdoor dungeon, a wilderness) with what to look for: versions and stepping
through them, reroll decor and rooms, Use in zone changing one room, times, and the files a
version holds. Run the thorough profile once.

## Done when
- [ ] The section is written, each case with its seed and what to check.
- [ ] The thorough run is green, or each failure is named and pre-existing.
      → verify: `python -m pytest tests/ -q --hypothesis-profile thorough`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Write what a person sees, not what a test checks. Don't commit while the thorough run runs.

## Result
✔ HASH · 3248 passed, thorough profile (on master 46a2877)
