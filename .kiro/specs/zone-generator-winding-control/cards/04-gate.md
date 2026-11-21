# 4 — Gate and bands

Index entry: `tasks.md` task 4. Requirement 6.

## Goal
Winding at 0, 1 and `WINDING_MAX` keeps every cave and warren build navigable and in its bands.

## Done when
- [x] `scripts/sweep_themed_navigability.py --only cave warren --layouts classic graph --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23`
      with `EQ_PATH` set, at each of the three settings: ≥ 691/696, the failures named (step 23's
      five residuals expected). If the sweep has no winding flag, add one in a script-only commit.
- [x] `quality_sweep --per-key 200 --only dungeon --seed 23` for cave and warren at `WINDING_MAX`:
      every key under 5%.
- [x] `python -m pytest tests/ -q -n 4` (full, alone) green.

## Pitfalls
- A new failure: stop and report before fixing or moving goldens.

## Result
✔ 7149e01 70521d1 948d9cc · gate 692/696 at Winding 0/1/2 · bands < 5% · 4066 passed
