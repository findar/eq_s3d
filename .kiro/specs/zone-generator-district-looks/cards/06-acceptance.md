# 6 — Acceptance section

Index entry: `tasks.md` task 6.

## Goal
`docs/ACCEPTANCE.md` gets a "Step 22 — District looks" section with these cases:
- a cave District after a fortress District, and the reverse, where walls and decor change at the
  Threshold;
- a `cave` dungeon's light and dressing;
- a `cave` dungeon's ceilings;
- a one-District dungeon, unchanged.

## Done when
- [ ] The section is written, and every case has been run through the route with its seed, using
      agent servers on 8020–8050 only. → verify: `git show HEAD -- docs/ACCEPTANCE.md`
- [ ] Thorough run: `python -m pytest tests/ -q --hypothesis-profile=thorough`, with any failures
      named in the commit body.

## Pitfalls
- Leave the user's servers (8000, 5173) and the lead's (8010, 5180) alone.
- Never write "Vite" or "dev server" in a commit message.

## Result
