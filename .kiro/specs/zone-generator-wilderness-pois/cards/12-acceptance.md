# 12 — Acceptance section, thorough run

Index entry: `tasks.md` task 12.

## Goal
A "Step 10 — Wilderness POIs" section in `docs/ACCEPTANCE.md`: pinned cases (seeds and controls) for each kind, Inhabitant, density and outdoor dungeons, with checks; a thorough run; the frontend builds.

## Done when
- [ ] Every pinned case builds first try and shows what its row says.
- [ ] The thorough suite is green.
      → verify: `python -m pytest tests/ -q --hypothesis-profile thorough`

## Pitfalls
Recheck every case on the final code before landing.

## Result
✔ 5603f25 · 2078 passed, 4 failed (thorough; 3 pre-step-10, 1 timing under load)
