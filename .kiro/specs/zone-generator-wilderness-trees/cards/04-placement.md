# 4 — Tree placement: eligible ground, groves, clearance

Index entry: `tasks.md` task 4. Design: "Placement", "Walkability".
Requirements 4, 5.

## Goal
`place_trees(land, ter, kit, level, seed)` returns Tree_Instances on eligible
TER quads, clustered into groves, with every trunk clear of other trunks and of
ineligible ground by Tree_Clearance.

## Done when
- [ ] Properties T2, T3 and T4 hold over seeds × Rim declarations × levels on
      synthesized landscapes (`synthesize_landscape` + `build_wilderness_ter`).
- [ ] `none` returns no instances (Req 4.4).
- [ ] The same inputs give the same instances; a different level never changes
      the TER (placement uses its own salted stream).
- [ ] The Karana measurement scripts' method is recorded in the commit body (how
      0x15 placements and 0x36 object meshes were read), so the design's
      research numbers can be re-derived.
      → verify: `python -m pytest tests/test_vegetation_placement.py -q`.

## Pitfalls
- Eligibility is per TER quad (both triangles), not per fine cell; the fine
  grid and the matrix are offset (step 1's known 150/160 u drift).
- Never loop per pixel or per quad in Python where numpy does it; a spatial hash
  for the dart test is fine.
- If Grove_Ratio can't land in band without hurting density, say so with
  numbers; don't widen the band silently.

## Result
