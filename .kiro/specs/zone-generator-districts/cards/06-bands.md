# 6 — Bands for Districts

Index entry: `tasks.md` task 6. Requirement 5. Design "Quality".

## Goal
The band key gains the resolved District count; `scripts/quality_sweep.py --districts` measures
districted dungeons (k = 2, 3; both layouts; each verticality; 8–30 rooms); their rows filled by
step 19's decision 4 rule; `district_balance` bounded on its low side.

## Done when
- [ ] The sweep runs. → verify: `python scripts/quality_sweep.py --per-key 40 --only dungeon --districts`
- [ ] Rows for k ≥ 2 filled; per key, the fail share and expected Draws per generate in the
      commit body; k = 1 rows unchanged. → verify: `python -m pytest tests/test_quality.py -q`
- [ ] `archive.md` decision 11 gives the rule in one or two lines.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Look at a few failing districted specs' maps before calling them dull. Keep the sweep's CSV in
`output/`, not committed.

## Result
