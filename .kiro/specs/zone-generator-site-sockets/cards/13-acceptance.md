# 13 — Acceptance section, thorough run

Index entry: `tasks.md` task 13.

## Goal
`docs/ACCEPTANCE.md` gains "Step 13 — Point Site Sockets": pinned cases for the human pass (wilderness hamlets at Normal and Dense, an outdoor dungeon's Site on its hill, a rooms reroll moving Sites among points, the map's points), each with what to look for. Re-check the step 10 and step 12 pinned cases that build Sites, and note in their sections which now look different and why. Run the thorough profile once.

## Done when
- [ ] The section is written, each case with its seed and what to check; the step 10 and 12 cases noted.
- [ ] The thorough run is green, or each failure is named and pre-existing.
      → verify: `python -m pytest tests/ -q --hypothesis-profile thorough`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Write what a person sees, not what a test checks.

## Result
