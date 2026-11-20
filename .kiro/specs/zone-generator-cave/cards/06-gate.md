# 6 — Gate and bands

Index entry: `tasks.md` task 6. Requirement 5. Design "Gate and bands".

## Goal
`cave` dungeons pass the traversability gate on both layouts; their quality fail share against
today's bands is measured (A3).

## Done when
- [ ] `scripts/sweep_themed_navigability.py` with `cave`, both layouts, 2–30 rooms, each
      verticality: every build passes; counts in the commit body.
- [ ] ≥ 200 `cave` Draws per layout: fail share and expected Draws per generate per key in the
      commit body; above ~5% on a key, a `cave` band row and an `archive.md` decision. → verify:
      `python -m pytest tests/test_quality.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
A gate failure is a geometry bug to fix at its root (project rule), named in the commit body; if
the fix is outside `Owns`, stop and report. Keep sweep CSVs in `output/`.

## Result
