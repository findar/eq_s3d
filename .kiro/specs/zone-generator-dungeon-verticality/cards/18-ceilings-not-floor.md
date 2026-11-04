# 18 — The gate stops reading ceilings as floor

Index entry: `tasks.md` task 18. Requirements 2, 4.3, 6.2. Added after task 5 (found by it).

## Goal
`analyzer.traverse.build_walk_surface` takes a downward-facing face as standable (it tests |nz|), and `corridor_conflicts` reads a corridor's ceiling as floor. Since step 6 it's been a follow-up; with stacked levels it costs real connections: task 5 had to keep corridors on adjacent Levels apart by max(Slab, corridor height + 1), and stacked builds keep 0.85 of their edges against 0.93 unstacked. Make the walk surface floors only (faces wound up), drop task 5's extra clearance, and retire task 5's `is_stacked_build` condition by updating task 2's test to the Slab rule.

## Done when
- [ ] The walk surface and `corridor_conflicts` use only upward-facing floor faces; ceilings never count as floor. A test builds a corridor over another (one Slab apart) and checks the lower ceiling is not walkable and no conflict is reported.
- [ ] `test_deck_over_a_low_halls_roof_still_crosses` (task 2) follows the Slab rule, and `is_stacked_build` goes: the over/under exemption applies to every spec.
- [ ] Task 5's corridor clearance between adjacent Levels drops to the Slab; stacked builds' Edge_Fidelity is measured before and after (in the commit body) on task 5's sweep and doesn't fall.
- [ ] Every existing gate result on single-level builds is unchanged (classic and graph goldens, the step 5 and 6 build tests, task 2's and 3's connector tests).
      → verify: `python -m pytest tests/test_traverse_ceilings.py tests/test_traverse_connectors.py tests/test_layout_levels.py tests/test_layout_engine.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- The box builder winds floors up and ceilings down (task 2 relied on it); stock WLD meshes can differ (step 6 survey). Keep the walk on our own TERs to winding; say what changes for WLD walks.
- A face that is both (a thin slab's top seen from above) is floor; only its underside is ceiling.

## Result
