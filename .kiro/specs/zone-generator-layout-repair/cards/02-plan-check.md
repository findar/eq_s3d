# 2 — Check the plan before the mesh

Index entry: `tasks.md` task 2. Requirement 2. Refined from task 1 before it starts.

## Goal
A plan check over the laid-out ZoneSpec catches the plan-visible failure classes task 1 found, before geometry.

## Done when
- [ ] One check per plan-visible class from task 1, each naming the gate reason it predicts.
- [ ] Measured on task 1's job set: catches (true positives), misses, and false refusals (plans the gate would pass); false refusals 0, or each named and accepted by the lead.
- [ ] Wired into `generate_validated` so a refused plan never reaches the mesh; whole-generate time before/after.
- [ ] Quick tier; `-m gate` and the full suite alone at close.

## Result
