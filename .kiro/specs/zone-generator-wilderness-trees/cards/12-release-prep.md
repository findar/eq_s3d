# 12 — Acceptance section, thorough run, timing

Index entry: `tasks.md` task 12. Requirement 11.2, exit criteria 1–2.

## Goal
`docs/ACCEPTANCE.md` gains "Step 2 — Trees", the timing test proves Req 11.2,
and the thorough profile is green.

## Done when
- [ ] The acceptance section covers every person-judged item: groves, grounding,
      exclusions, trunk solid / canopy walk-through (noting the in-client check
      is M6 and the preview shows card canopies in base colour), the selector
      and the toggle.
- [ ] A `slow` timing test: a `dense` build adds at most 3 s over `none`.
- [ ] The fast and thorough suites pass.
      → verify: `python -m pytest tests/ -q` and
        `python -m pytest tests/ -q --hypothesis-profile=thorough`.

## Pitfalls
- The thorough run takes about 20 minutes; run it in the background.
- A thorough failure that isn't a tree bug becomes a new task, as step 1b's
  task 15 did.

## Result
