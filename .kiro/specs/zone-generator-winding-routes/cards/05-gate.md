# 5 — Gate and bands

Index entry: `tasks.md` task 5. Requirement 6.

## Done when
- [x] With `EQ_PATH='F:\everquest_rof2'` set,
      `python scripts/sweep_themed_navigability.py --only cave warren --layouts classic graph --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23`
      passes at least master's count before this step (archive.md "Decisions" 3), every new
      failure fixed at its root.
- [x] 200 Draws per layout: fail share per key in the commit body, each under ~5% or an
      `archive.md` decision. → verify: `python -m pytest tests/test_quality.py -q`
- [x] `python -m pytest tests/ -q` is green, run once with nothing else running.

## Result
✔ 1d18c74 7c7330e 2a2ec33 0946cb6 · 4041 passed · gate 691/696 · fail share ≤ 4.5%
