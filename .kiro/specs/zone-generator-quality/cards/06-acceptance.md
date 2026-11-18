# 6 — Acceptance section

Index entry: `tasks.md` task 6.

## Goal
`docs/ACCEPTANCE.md` "Step 19 — Quality": a passing generate, a pinned seed outside the bands (the
banner, the list), an old version (quality unknown), an edit outside the bands, and a few redrawn
seeds' maps beside passing ones to judge whether the bands catch dull layouts.

## Done when
- [ ] The section is written, every case run through the route. → verify:
      `git show HEAD -- docs/ACCEPTANCE.md`
- [ ] Thorough run: `python -m pytest tests/ -q --hypothesis-profile=thorough`, with any failures
      named in the commit body.

## Result
