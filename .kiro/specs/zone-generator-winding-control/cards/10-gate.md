# 10 — Gate and bands again

Index entry: `tasks.md` task 10. Requirement 6.

## Goal
Tasks 8 and 9 keep every cave and warren build navigable and in its bands.

## Done when
- [x] The task 4 gate sweep (`--only cave warren --layouts classic graph --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23`, `EQ_PATH` set) at Winding 0, 1 and 2: ≥ 692/696, failures named.
- [x] `quality_sweep --per-key 200 --only dungeon --seed 23` for cave and warren at Winding 1 and 2: every key under 5%.
- [x] `python -m pytest tests/ -q -n 4` (full, alone) green.

## Pitfalls
- A new failure: stop and report before fixing or moving goldens.

## Result
✔ 7566697 131f3a2 74ae74e · gate 693/696 at Winding 0/1/2 · bands < 5% · 4100 passed
