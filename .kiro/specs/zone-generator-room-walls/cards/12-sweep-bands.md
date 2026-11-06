# 12 — Gate sweep and stock bands

Index entry: `tasks.md` task 12. Requirements 12.

## Goal
W11 and W12 on built zones, with `scripts/wall_survey.py`'s own measures. Tune the style files to the bands. Measure how much smaller rooms read (design Risks), for Open question 4.

## Done when
- [ ] Built zones per style in their bands, in the right order, over seeds.
- [ ] First-try rate at least step 7's across styles, rule sets, themes, races, Verticality; same inputs same `.eqg`; time within step 7 + 10 s.
      → verify: `python -m pytest tests/test_walls_build.py -q`
- [ ] The commit body gives rates, bands and the effective room sizes.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Step 6 and 7's bands (fidelity, stacked share) must still hold. Fix root causes, not bands.

## Result
