# 9 — Acceptance section, thorough run

Index entry: `tasks.md` task 9.

## Goal
`docs/ACCEPTANCE.md` gains "Step 17 — Export", with pinned cases: a dungeon with Locks 2, a city,
an outdoor dungeon and a wilderness. For each, what to look for:
- the picker and exporting;
- the bundle's files and the SQL;
- two exports of one build;
- the in-client load steps (copy into a scratch copy of the install, enter `arena`).

Run the thorough profile once.

## Done when
- [ ] The section is written, each case with its seed and what to check.
- [ ] The thorough run is green, or each failure is named and pre-existing.
      → verify: `python -m pytest tests/ -q --hypothesis-profile thorough`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Write what a person sees, not what a test checks. Don't commit while the thorough run runs.

## Result
