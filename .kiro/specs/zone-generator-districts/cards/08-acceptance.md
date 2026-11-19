# 8 — Acceptance section

Index entry: `tasks.md` task 8.

## Goal
`docs/ACCEPTANCE.md` "Step 20 — Districts": a districted dungeon on each layout (map hulls,
Thresholds, the palette and light change walking across a Threshold in 3D, one boss per
District), a prompt that turns them on, locks on Thresholds, a pinned single Purpose, and the
switch off giving the zone it always did.

## Done when
- [ ] The section is written, every case run through the route. → verify:
      `git show HEAD -- docs/ACCEPTANCE.md`
- [ ] Thorough run: `python -m pytest tests/ -q --hypothesis-profile=thorough`, with any failures
      named in the commit body.

## Result
