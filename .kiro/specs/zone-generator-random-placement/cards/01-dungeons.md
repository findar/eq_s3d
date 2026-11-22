# 1 — Measure, and jitter every built and hewn Graph dungeon

Index entry: `tasks.md` task 1. Requirements 1, 2, 5, 6. Design "Approach", "Measuring set".

## Goal
Every Graph dungeon theme (warrens aside, task 2) places its rooms off the lattice, joined as
before, from the build's own seed.

## Done when
- [ ] `scripts/grid_score.py` prints, per theme, grid score, door-to-door median,
      `relations_broken`, `edge_fidelity`, cycles and dead ends over seeds 2000–2039; the
      before (`b77d5a9`) and after tables are in the commit body.
- [ ] Every non-warren theme: grid mean ≤ 0.10, door-to-door median ≤ 4/3 of before, shape
      bands green (`python -m pytest tests/test_topology_levels.py -q`).
- [ ] The jitter salt uses the build's seed (two seeds with the same rooms place differently; a
      test in tests/test_topology_embed.py).
- [ ] The byte check in `tasks.md` passes; `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q -n 4`
      (alone) green, each moved golden named in the commit.

## Pitfalls
- Winding-control archive decision 5 and its task 8 first attempt (design "Starting point"):
  start from the slack-bounded offset and straight doors.
- A new gate failure that this causes is fixed here at its root; stop and report one that needs
  files outside Owns.

## Result
✔ b4b8822 · 4102 passed
