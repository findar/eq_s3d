# 3 — The winding mesh

Index entry: `tasks.md` task 3. Requirement 3. Design "The mesh".

## Goal
A plain leg with `wind > 0` is built along `wind_leg`'s centreline:
- a mitred floor strip;
- walls with the rough wobble;
- a ceiling that follows the strip;
- ends that weld to the square bends and room openings.

## Done when
- [x] Over 10 cave dungeons and 5 warren dungeons (graph layout, 8–30 rooms, each verticality):
      every build passes the traversability gate, and the mesh has no open seam where a winding
      leg meets a bend or room. → verify: `python -m pytest tests/test_winding_mesh.py -q`
- [x] Look at 3 builds' meshes, and the map SVG (`generators/mapview.py`) of each. Say what you
      saw in the commit body.
- [x] The byte check passes for zones with no rough corridor. Goldens of rough zones are
      recaptured in their own commit, naming each.
- [ ] `python -m pytest tests/ -q -m "not slow"` is green. (left for the lead: runs after the merge)

## Pitfalls
- Read lessons-learned "A ramp must be SUBDIVIDED": every floor triangle's rise stays
  within the gate's step.
- `generators/geometry.py` is large; touch only the leg builders and `_emit_route`'s dispatch.

## Result
✔ 24af605 · 26 passed, 5 skipped (warrens don't wind) · byte check 105 passed, no golden moved
