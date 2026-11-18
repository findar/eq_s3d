# 3 — The gate in the pipeline

Index entry: `tasks.md` task 3. Requirements 3 and 6. Design "Pipeline".

## Goal
Umbrella 24.5–24.8 in `generate_validated`; the sidecar `quality` entry; measure-only for
rebuilds and edits (A4).

## Done when
- [ ] With injected bands: an unpinned seed redraws until a pass and builds only that Draw; 32
      failures build the lowest score as `quality_degraded`; a pinned failure builds once as
      `quality_outside_bands_pinned`; a hard-gate failure after the loop retries with no quality
      Draws; the timeout cuts the Draws short. → verify:
      `python -m pytest tests/test_quality_gate.py -q`
- [ ] The sidecar's `quality` equals `quality_summary` of the returned report; rebuilds measure
      without redrawing. Same command.
- [ ] The byte check in `tasks.md` passes (geometry unchanged; any recaptured golden moved for
      the `quality` entry alone, named in the commit body).
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Count Draw time inside the existing timeout. Keep the World/rooms/decor stage reroll logic as it
is (`_blame`, `MAX_STAGE_REROLLS`). Don't commit while the full suite runs.

## Result
