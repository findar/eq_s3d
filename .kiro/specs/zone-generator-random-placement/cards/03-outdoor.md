# 3 — Outdoor dungeons

Index entry: `tasks.md` task 3. Requirements 1, 2. Design "Approach" (Outdoor dungeon).

## Goal
Outdoor dungeon rooms leave the lattice inside their Envelope, with their stairs and Levels
intact.

## Done when
- [ ] Outdoor-dungeon grid mean ≤ 0.10 over seeds 2000–2039; door-to-door median ≤ 4/3 of before.
- [ ] `python -m pytest tests/test_outdoor_levels.py -q` green (entrance on the top Level, dragon
      stairs stay in the bowl); seed 1654615998 passes the gate.
- [ ] `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q -n 4` (alone) green.

## Pitfalls
- `fit_to_envelope` and `layout_in_envelope`: an offset must not push a room out of the hill.

## Result
