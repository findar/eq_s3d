# 8 — Acceptance section

Index entry: `tasks.md` task 8.

## Goal
`docs/ACCEPTANCE.md` "Step 18 — Edits": the umbrella's scripted session (a bigger boss room, or
without resize the boss room's purpose → lock the way into the crypt → redecorate the entrance
→ undo → redo) with what to look for, including the rooms outside each edit visibly unchanged.

## Done when
- [ ] The section is written. → verify: `git show HEAD -- docs/ACCEPTANCE.md`
- [ ] Thorough run: `python -m pytest tests/ -q --hypothesis-profile=thorough`, with any failures
      named in the commit body.

## Result
