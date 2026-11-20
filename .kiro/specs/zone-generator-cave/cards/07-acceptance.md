# 7 — Acceptance section

Index entry: `tasks.md` task 7.

## Goal
`docs/ACCEPTANCE.md` "Step 21 — Caves": a `cave` dungeon on each layout (wandering `rough`
walls, cold light, crystal climax, water in flooded galleries, decor), a prompt that picks it
("a dark cavern"), a cave District next to a built one, another Purpose unchanged.

## Done when
- [x] The section is written, every case run through the route with its seed. → verify:
      `git show HEAD -- docs/ACCEPTANCE.md`
- [x] Thorough run: `python -m pytest tests/ -q --hypothesis-profile=thorough`, failures named
      in the commit body.

## Result
✔ bae1ae8 · 3799 passed (thorough), no failures
