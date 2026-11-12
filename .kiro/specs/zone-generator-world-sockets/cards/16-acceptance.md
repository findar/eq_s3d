# 16 — Acceptance section, thorough run

Index entry: `tasks.md` task 16.

## Goal
`docs/ACCEPTANCE.md` gains "Step 12 — World Sockets": pinned cases for the human pass (an outdoor dungeon and a wilderness rerolled on rooms; zones step 11 built, unchanged; the Sockets on the map; the stage commands), each with what to look for. Run the thorough profile once.

## Done when
- [ ] The section is written, each case with its seed and what to check.
- [ ] The thorough run is green, or each failure is named and pre-existing (step 11 left one: `test_properties_mapgeom.py::test_reachable_only`).
      → verify: `python -m pytest tests/ -q --hypothesis-profile thorough`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Write what a person sees, not what a test checks.

## Result
