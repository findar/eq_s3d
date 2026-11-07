# 11 — Gate sweep and stock bands

Index entry: `tasks.md` task 11. Requirements 9.

## Goal
F9 and F10 with `scripts/room_feature_survey.py`'s own measures. Tune density to the bands.

## Done when
- [x] Built zones per style in bands, by room size.
- [x] First-try rate at least step 8's across styles, densities, rule sets, themes, races, Verticality; same inputs same `.eqg`; time within step 8 + 5 s.
      → verify: `python -m pytest tests/test_features_sweep.py -q`
- [x] The commit body gives rates, bands, drops and timing.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Earlier steps' bands must hold. Fix root causes, not bands. A timing test under the parallel suite needs CPU time and care (step 8 task 12).

## Result
✔ ee48071 · 1811 passed
