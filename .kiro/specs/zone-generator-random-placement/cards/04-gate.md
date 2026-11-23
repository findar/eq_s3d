# 4 — Gate and bands

Index entry: `tasks.md` task 4. Requirement 4.

## Goal
Random placement keeps every Graph zone navigable and in its bands.

## Done when
- [ ] `scripts/sweep_themed_navigability.py --only cave warren --layouts classic graph --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23`
      with `EQ_PATH` set: ≥ 693/696, failures named.
- [ ] The same sweep over the other dungeon themes (`--only fortress tomb temple mine_delve` and
      the rest, `--layouts graph`) and the outdoor dungeon: the count before (`b77d5a9`) and
      after, every new failure named.
- [ ] `quality_sweep --per-key 200 --only dungeon --seed 23` and the outdoor dungeon's: every key
      under 5%.
- [ ] `python -m pytest tests/ -q -n 4` (full, alone) green.

## Pitfalls
- A new failure: stop and report before fixing or moving goldens.

## Result
✔ f0102aa · 4107 passed
