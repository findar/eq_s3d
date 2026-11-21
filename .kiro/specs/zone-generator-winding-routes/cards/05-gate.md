# 5 — Gate and bands

Index entry: `tasks.md` task 5. Requirement 6.

## Done when
- [ ] With `EQ_PATH='F:\everquest_rof2'` set,
      `python scripts/sweep_themed_navigability.py --only cave warren --layouts classic graph --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23`
      passes at least master's count before this step (archive.md "Decisions" 3), every new
      failure fixed at its root.
- [ ] 200 Draws per layout: fail share per key in the commit body, each under ~5% or an
      `archive.md` decision. → verify: `python -m pytest tests/test_quality.py -q`
- [ ] `python -m pytest tests/ -q` is green, run once with nothing else running.

## Result
