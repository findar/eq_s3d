# 10 — Acceptance section, thorough run, timing

Index entry: `tasks.md` task 10. Requirement 8, exit criteria 1–2.

## Goal
`docs/ACCEPTANCE.md` gains "Step 4 — Interesting textures", the timing test
proves Req 8, and the thorough profile is green.

## Done when
- [ ] The acceptance section covers every person-judged item: material
      reading, classic look, scale, repetition and seams, themes differing,
      the mode overrides, and that the in-client check is M6.
- [ ] A `slow` timing test (Y7): recipe textures add at most 2 s over
      placeholders on a dense wilderness build.
- [ ] The fast and thorough suites pass.
      → verify: `python -m pytest tests/ -q` and
        `python -m pytest tests/ -q --hypothesis-profile=thorough`.

## Pitfalls
- The thorough run takes about 20 minutes; run it in the background.
- lessons-learned: the parallel runner occasionally stumbles; re-run before
  debugging. A failure that repeats and isn't a texture bug becomes a new task.

## Result
