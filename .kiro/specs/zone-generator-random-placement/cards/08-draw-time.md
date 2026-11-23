# 8 — Outdoor draw time

Index entry: `tasks.md` task 8. Found by task 4; north-star: generation under ~5 minutes.

## Goal
Task 3's Envelope jitter makes big outdoor graph draws several times slower; bring them back
near `b77d5a9` without putting rooms back on the lattice.

## Done when
- [ ] Seeds timed at `b77d5a9`, `7e5f41d` and after, in the commit body: corrupted_sanctum 30
      s1078956947 (129 s / 539 s) and warren 27 s1145360150 (63 s / 408 s), plus the p95 and max of
      outdoor graph flat 27–30 room draws over the task 4 sample. After: each seed at most 1.5x its
      `b77d5a9` time, and no draw over 300 s.
- [ ] Task 3's targets still hold (`scripts/grid_score.py` or task 3's `od_grid.py` over outdoor
      graph seeds 2000–2039): grid mean ≤ 0.10 per theme, door-to-door p50 ≤ 4/3 of before.
- [ ] `EQ_PATH='F:\everquest_rof2' python scripts/sweep_themed_navigability.py --outdoor --layouts graph --rooms 2-30 --seeds 2 --seed 23 --verticality flat moderate dramatic` ≥ 173/174.
- [ ] `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q -n 4` (full, alone) green.

## Pitfalls
- Profile first; name the cause in the commit (the entry re-draws, the Envelope fit's retries, or
  layout attempts failing more often off the lattice).
- Don't trade the grid score or the entrance rule for speed without reporting.

## Result
✔ e319c13 · 4108 passed
