# 2 — Ground the takeover and the doors

Index entry: `tasks.md` task 2. Requirement 3.3. Design "Doors".

## Goal
Answer from the install (read-only), and record the answers in `docs/RESEARCH.md` ("Step 17:
takeover and doors") and as decisions in `archive.md`:

1. **Which archive the client loads** for a short name that has both `<short>.s3d` and
   `<short>.eqg` (+ a loose `<short>.zon`), as `arena` does. Count how many stock zones have both,
   and what the loose `.zon` points at. If the install alone can't settle it, say what the user
   must check in the client (that check goes into task 10), and give install steps that work
   either way (move both aside).
2. **What a door row's `name` names.** Survey stock `.eqg` zones and their `_obj`/`_chr`
   archives for door models (names with DOOR, GATE, PORTC...) and how they are packed. Decide
   the Door model our takeover names: a global model the client always loads, or one packed into
   our `.eqg` (then task 5 packs it). Name the model, its source archive and its size.
3. **The door row's fields** for a plain locked door: `opentype`, `size`, `heading` units
   (EQEmu's 0–512 or degrees), `incline`, from the pinned columns (decision 4) and EQEmu's docs.

A grounding test (`tests/test_export_grounding.py`, skipped without an install) pins the facts
the code will rely on: the chosen Door model exists where you say.

## Done when
- [x] The three answers are in `docs/RESEARCH.md` with the evidence (counts, archive names).
- [x] `archive.md` "Decisions" gains one line each for the load rule, the Door model and the
      door fields.
- [x] `python -m pytest tests/test_export_grounding.py -q` passes (skips without the install).

## Pitfalls
Read only: never write under `EQ_PATH`. Built `.eqg` files and client art never get committed.
Don't guess the client's behaviour: if the install can't show it, say it is unverified.

## Result
✔ c2e85f0 · grounding test passes
