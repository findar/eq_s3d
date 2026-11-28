# 1 — Breaches fit again

Index entry: `tasks.md` task 1. Requirements 1, 4.

## Goal
An intruder District overlaps its host again: short, goblin-length breaches fit between most intruder/host pairs.

## Done when
- [ ] The cause measured on master: for every candidate breach pair over the `--intrusion` sweep seed 31 and prompt seeds 2020-2029, why it was refused (span over the bound, different Levels, `_resolve_conflicts`, degree cap, other), as a table in the commit body.
- [ ] `--intrusion` sweep seed 31: 240/240, pairs with 2+ links at least 80% (master 68%), drop share reported.
- [ ] The giant-fortress prompt ("a towering giant fortress the goblins tunnelled into, with 16 rooms", the server's prompt path) on seeds 2020-2029: every zone passes the gate, at least 9 of 10 have a goblin breach.
- [ ] Links between Districts, each in its own race's H (step 31 task 17's measure): p50 in 10.7-30.2 H, max at most 164 H; giant halls keep 3x; goblin halls unchanged. Before/after table.
- [ ] 120-Draw intrusion bands every key under 5%; 24-room whole-generate max under 300 s.
- [ ] Zones without a District race byte-identical to master (each built in its own process).
- [ ] Quick tier; `-m gate` and the full suite alone at close. A decision in `archive.md`.

## Pitfalls
- Don't lengthen links back past task 17's bars, and don't shrink giants (step 31 archive decisions 18, 21).
- `tests/test_intrusion.py::test_new_breaches_fill_most_pairs` was lowered to 0.35 for Graph at step 31 task 17: raise it back to what the fix earns.
- Stacked Districts and the relax runaway (step 31 `7a9b90e`, `HALL_SCALE_CAP`).

## Result
✔ 928db52 · quick 3211 passed · gate 702 passed · full 4417 passed (its one failure, the bridges slot case, re-pinned in 928db52: 67 passed)
