# 2 — One-way navigation in the gate

Index entry: `tasks.md` task 2. Requirements 2.

## Goal
The gate reads a drop as a one-way link and passes a zone only if it is strongly connected from the entrance; a zone with no drop gets exactly today's report.

## Done when
- [ ] A directed pass in `analyzer/traverse.py`: an open floor edge with walkable floor 3 u to `MAX_DROP` below (no wall between) links upper -> lower; reachability is a forward flood from the entrance and a backward flood to it, both over every room.
- [ ] `tests/test_traverse_directed.py`: a hand-built mesh with a drop-only way in and a flush way back passes; the same with no way back fails, naming the stranded room; a drop above `MAX_DROP` is a wall.
- [ ] Report identity: the step 28 comparison script over the cave/warren sweep (`scripts/sweep_themed_navigability.py --only cave warren --layouts classic graph --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23 --jobs 6`) gives identical pass/fail and reasons to master, and 694+ pass.
- [ ] Gate time on a 30-room cave within 10% of master (say the numbers).
- [ ] Quick tier while working; `-m gate` and the full suite alone green at close.

## Pitfalls
- lessons-learned "A ramp must be SUBDIVIDED" (centroid steps) and the gate's seam-contact slack: a ramp must not read as a drop.
- Stairs: a stair's riser is a step up, not a drop; keep stairs two-way.
- If a generator change seems needed, stop and report.

## Result
✔ 2b65b08 · 4242 passed
