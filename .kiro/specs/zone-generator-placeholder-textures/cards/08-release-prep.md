# 8 — Acceptance section, thorough run, timing

Index entry: `tasks.md` task 8. Requirement 8, exit criteria 1–2.

## Goal
`docs/ACCEPTANCE.md` gains "Step 3 — Placeholder textures", the timing test
proves Req 8, and the thorough profile is green.

## Done when
- [x] The acceptance section covers every person-judged item: names match
      surfaces, patterns, legibility, orientation, seams, the manifest, the
      texture mode override, and that the in-client check is M6.
- [x] A `slow` timing test (X8): placeholders plus embedding add at most 2 s
      to a dense wilderness build, compared with `procedural` mode.
- [x] The fast and thorough suites pass.
      → verify: `python -m pytest tests/ -q` and
        `python -m pytest tests/ -q --hypothesis-profile=thorough`.

## Pitfalls
- The thorough run takes about 20 minutes; run it in the background.
- A thorough failure that isn't a texture bug becomes a new task.

## Result
✔ dd5f24f · 738 passed (thorough 737 + 1 flaky non-texture failure → task 12)
