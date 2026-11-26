# 3 — Advisory gates and pacing on the directed graph

Index entry: `tasks.md` task 3. Requirements 3.

## Goal
Lock-and-key placement and `solvable` treat a drop as one-way, so a key is never behind a drop with no way back to its lock.

## Done when
- [ ] Gating and `edits.solvable` take directed edges (a corridor with `drop` is one-way; none exist yet, so tests build them by hand).
- [ ] `tests/test_gating_directed.py`: a gate whose key sits past a one-way loop is solvable; one whose key needs climbing a drop is not.
- [ ] Every zone byte-identical (no drops exist yet): the step 27 byte check.
- [ ] Quick tier green; full suite alone at close.

## Pitfalls
- Gates are suggestions: nothing here touches geometry or collision (project.md).

## Result
✔ f93925e · 4303 passed (3 test_quality Hypothesis failures under load; 27/27 alone)
