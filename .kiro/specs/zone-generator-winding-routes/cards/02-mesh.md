# 2 — The mesh along the path

Index entry: `tasks.md` task 2. Requirement 3. Design "Mesh".

## Goal
A corridor with a `path` is built as one winding strip from opening to opening, its rise spread
over the path between the run-outs.

## Done when
- [x] Over 10 cave and 5 warren graph builds (8–30 rooms, each verticality) every build passes the
      traversability gate and no piece of a path's floor rises more than `MAX_SEG_RISE`. → verify:
      `python -m pytest tests/test_wind_route_mesh.py -q`
- [x] `corridor_continuity` reads the path's segments.
- [x] Look at 3 builds' meshes and map SVGs; say what you saw in the commit body.
- [x] The byte check passes for zones with no rough corridor; rough goldens recaptured by name.
- [x] `python -m pytest tests/ -q -m "not slow"` is green.

## Pitfalls
- lessons-learned "A ramp must be SUBDIVIDED" and "Same-axis room pairs need a Z-route".
- Reuse `_add_winding_leg`'s strip; `geometry.py` is large, so touch only the route dispatch.

## Result
✔ 7e6c7dc · 31 passed (test_wind_route_mesh) · not-slow 3112 passed on master after merging tasks 2 and 3
