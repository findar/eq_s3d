# 18 — Loops survive placement

Index entry: `tasks.md` task 18. Requirements 5.1, 6.4. Added after task 8 (found by it).

## Goal
The loops the rules grow must survive corridor routing. After task 8, built dungeons keep almost none of them: over seeds 0–11 × rooms 10/15/20/25, Edge_Fidelity is 0.887 (`classic_eq`) and 0.817 (`warren`, under the 0.85 bar), and the BUILT graph's cycles per room are 0.038 and 0.045 against the survey bands 0.07–0.25 and 0.19–0.29. Task 8 found 171 of 232 loop edges dropped against 46 of 1600 tree edges.

## Done when
- [ ] The cause is measured per drop (crossing split, conflict drop, which corridor shapes) and written in the commit body.
- [ ] Edge_Fidelity ≥ 0.85 for both base sets and the temple theme over the task 8 sweep; the G8 test covers all three.
- [ ] The built graph's cycles per room (corridors after Job B, not the grammar graph) falls in each set's survey band on the sweep mean; a test asserts it. Dead-end share and deep-end distance of the built graph stay in band too.
- [ ] Task 2's goldens pass (classic untouched).
      → verify: `python -m pytest tests/test_topology_embed.py tests/test_ruleset_classic_eq.py tests/test_ruleset_warren.py tests/test_layout_engine.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Task 8's diagnosis (its commit `1fbc058`): each corridor's exit wall is picked the same way from both ends, so corridors are straight or Z, never L; a ring of three then puts two corridors on one wall, their middle legs overlap past the shared doorway, and `_resolve_conflicts` drops the loop edge. Spring constants barely move it.
- Candidate fixes, cheapest first: rings of at least four in the rules (a triangle can't be drawn with axis-aligned corridors on separate walls; raise the driver's loop minimum to 4 if the rules alone can't hold it); placement that gives each of a room's neighbours its own side (degree ≤ 4 makes this possible) and keeps it through the springs and separation; only then the router's exit-wall choice, which classic also uses: any change there must leave classic byte-identical.
- Re-tune the rule sets' recipes if the loop rules change, and keep the grammar-graph bands (tasks 5, 6) passing as well as the built ones.
- project.md: fix the root cause; don't lower the bar.

## Result
