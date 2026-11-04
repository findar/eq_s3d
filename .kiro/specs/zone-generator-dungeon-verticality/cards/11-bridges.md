# 11 — Bridges

Index entry: `tasks.md` task 11. Requirements 2.1, 3.4. Design "Bridges". Only if Open question 1 keeps bridges in this step and the first look still wants them.

## Goal
A Bridge: a deck at the upper Level crossing a taller lower room's air, joining two upper rooms, with the lower room's ceiling opened under it; a `gallery`-style rule that grows one; the gate passes it (task 2's bridge checks).

## Done when
- [ ] Bridge geometry: flush at both ends, the ceiling opening under the deck, nothing to fall through except into the room below (which is reachable).
- [ ] A rule grows bridges; built bridge dungeons pass the gate over a seed sweep.
      → verify: `python -m pytest tests/test_bridges.py tests/test_traverse_connectors.py tests/test_vertical_build.py -q`
- [ ] `python -m pytest tests/ -q` is green; classic goldens unchanged.

## Pitfalls
- Falling off a bridge lands in the lower room: that room must be reachable on foot, or the gate's flood from the spawn is the wrong question (the player can drop, not climb back).

## Result
