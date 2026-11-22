# 2 — Warrens keep their loops

Index entry: `tasks.md` task 2. Requirements 1, 3. Design "Approach" (Warrens).

## Goal
Warren Graph zones leave the lattice and keep their loops and dead ends in band.

## Done when
- [ ] Warren grid mean ≤ 0.10 over seeds 2000–2039 and the cave/warren rule set's cycles and dead
      ends in band (`python -m pytest tests/test_topology_levels.py -q`); before/after in the
      commit body.
- [ ] Cave zones (warren rule set, cave profile) keep step 26's numbers or better: wind share
      ≥ 69%, path share ≥ 60% at Winding 1 over cave graph seeds 1000–1039.
- [ ] `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q -n 4` (alone) green.

## Pitfalls
- A loop edge whose rooms face on a used wall is dropped by Job B: keep the loop-closing rank
  on the un-offset position.

## Result
