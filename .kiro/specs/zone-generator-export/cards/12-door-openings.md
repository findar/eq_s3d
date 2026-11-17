# 12 — Doors that seal their corridor

Index entry: `tasks.md` task 12. Requirement 3.3 (amendment A3). Decision 11.

## Goal
`export_sql` puts each door row at the corridor's opening nearest the Gate's lock (where the
corridor meets a room's wall), turned across the doorway, hinge at one jamb, sized to the opening's
width, at the opening's floor height. Find the openings as the geometry does (`routing` and the
room walls; read how `geometry.add_corridor` and the layout cut doorways). The Gate's lock in the
spec and sidecar is unchanged.

## Done when
- [x] On the 40 dungeon seeds with 3 locks that task 4 swept, every door row lies on its
      corridor's opening (within 1 u of the doorway's line), spans jamb to jamb, and stands on the
      opening's floor. → verify: `python -m pytest tests/test_sqlexport.py -q`
- [x] Task 4's checks still pass (applied once and twice, header, transaction, columns). Same command.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
A corridor with elevation has two floor heights: take the opening's own. Which way the heading turns
in the client is unverified (task 10): keep task 4's convention and say so.

## Result
✔ d980bbe · 3269 passed
