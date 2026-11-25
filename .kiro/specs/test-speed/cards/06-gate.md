# 6 — A faster gate

Index entry: `tasks.md` task 6. Requirement 3; archive decision 3.

## Goal
The traversal gate (`analyzer/traverse.py`) does the same work in far less time, so every sweep
test and every generate gets faster. Task 2 profiled a moderate sweep build at about 50% in the
gate, mostly Python loops: `_tri_tri_xy_contact`, `_seg_seg_closest_xy`, `pt_seg` (about 1.4 s a
build).

## Done when
- [ ] The hot loops are vectorised (numpy) or pruned (a spatial index before the exact test);
      profile before and after on one moderate sweep build, in the commit body.
- [ ] Same verdicts: on at least 60 builds (cave, warren, fortress, temple, outdoor dungeon, city;
      flat, moderate, dramatic; seeds named), the gate's report is equal before and after (reachable
      sets, failure kinds, rooms named). The method goes in the commit body; a float tolerance only
      where the old code compared floats, named.
- [ ] `python -m pytest tests/ -q` alone, green; wall at `-n auto` in the commit body (task 2:
      1670 s; aim at 1300 s or less).
- [ ] `python -m pytest tests/ -q -m gate` green.

## Pitfalls
- lessons-learned "A ramp must be SUBDIVIDED": the step-up and centroid rules are the gate's
  meaning; keep them exact.
- Never reintroduce a per-element Python loop over all triangles (lessons-learned "Performance").
- If the speed-up needs builder or decor changes, stop and report.

## Result
