# 4 — The rules name the tiers

Index entry: `tasks.md` task 4. Requirement 4.

## Goal
Every agent runs the quick tier while working, and the full suite once at close.

## Done when
- [x] `project.md` "Run the suite before claiming done" names the tiers, each with its command
      and measured time: quick while working; full, alone, at close; `-m gate` after geometry,
      layout or gate changes.
- [x] lessons-learned gains a line on what the quick tier does not catch (gate sweeps, goldens
      of slow builds).
- [x] `grep -rn "pytest tests/" .kiro/steering CLAUDE.md` shows no command that contradicts the
      tiers.

## Result
✔ 1821513 · gate tier 1039 s, 702 passed
