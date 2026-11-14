# 8 — Acceptance section, thorough run

Index entry: `tasks.md` task 8.

## Goal
`docs/ACCEPTANCE.md` gains "Step 15 — Decor rule sets and the room view": pinned cases (a dungeon, a city, a tomb with and without an extra layer, a room view per kind of room) with what to look for; a walk-through of writing a small layer from `docs/DECOR_RULES.md` and seeing it in the room view with re-read rules. Run the thorough profile once.

## Done when
- [ ] The section is written, each case with its seed and what to check.
- [ ] The thorough run is green, or each failure is named and pre-existing.
      → verify: `python -m pytest tests/ -q --hypothesis-profile thorough`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Write what a person sees, not what a test checks.

## Result
