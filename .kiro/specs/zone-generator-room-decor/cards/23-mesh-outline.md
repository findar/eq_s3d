# 23 — Floor Props placed by their mesh outline

Index entry: `tasks.md` task 23. Found by task 22's full run: placement read every floor
model as its measured rectangle, while the gate reads its mesh. A round model's rectangle
reaches past its body, so (1) LROCK308 stood on the lowest floor under a rectangle corner
its body doesn't cover and sank 0.12 u into the floor under it (dungeon seed 4), and (2)
GKROCKS401 left floor between its body and a wall that placement counted as rock and the
gate as a pocket cut off (`footprint_cut`, graph warren plain, 16 rooms, build seed
242886303).

## Goal
Placement reads a floor (and raised) model's footprint from the mesh outline the gate uses
(the plan hull of its collidable triangles) for its floor height and for the "inside one
model's plan" exemption, so placement and gate agree on round models. The outline is
measured once into the catalogue (`outline`, written by `scripts/prop_catalogue.py
outline`), so this task also owns `rules/decor/catalogue.json` and
`scripts/prop_catalogue.py` (the new `outline` command and keeping the field on rebuild).

## Done when
- [ ] A test per failure mode, failing on the rectangle code: LROCK308 stands on the floor
      under its mesh; GKROCKS401 cuts no pocket by a wall.
      → verify: `python -m pytest tests/test_decor_placement.py tests/test_decor_builds.py -q`
- [ ] Bands and first try still hold, Normal and Dense.
      → verify: `python -m pytest tests/test_decor_bands.py -q -n 0`
- [ ] The three task 22 failures pass: `test_floor_props_stand_on_the_floor_under_them[dungeon]`,
      the dungeon-warren gate sweep and the stacked dungeon-warren-plain sweep.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Don't loosen either test and don't guess a rounder shape: measure the mesh. Check every
catalogue screen that judges a model by its plan (`open_ground`, decision 40) and rescreen
if its result changes. Placement must still agree with the gate (decisions 31, 47, 48).

## Result
