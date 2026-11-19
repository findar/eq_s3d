# 2 — Calibrate the bands

Index entry: `tasks.md` task 2. Requirement 2, amendments A1–A2. Design "Bands".

## Goal
`scripts/quality_sweep.py` draws specs (no builds) across every enabled zone type, both layouts,
each verticality and room counts 4–30, measures them and times each Draw. From that, fill the
band table in `generators/quality.py` and record the choice.

## Done when
- [x] The sweep runs. → verify: `python scripts/quality_sweep.py --per-key 40` (print its
      per-key quantiles; the CSV goes to `output/`, not committed)
- [x] The band table is filled; per key, the share of ordinary Draws failing and the expected
      Draws per generate are in the commit body, with the Draw times. → verify:
      `python -m pytest tests/test_quality.py -q`
- [x] `archive.md` decision 4 gives the bands' rule in two or three lines (the share allowed to
      fail, which metrics were dropped or left unbounded and why).
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
A key whose Draw is slow (outdoor dungeons build a World) needs a band loose enough that it
rarely redraws: say what a Draw costs there. Look at a few of the specs that fail before calling
them dull (the map SVG from `generators/mapview.py` is enough).

## Result
✔ 4b70a3e, ec5be17 · 3539 passed
