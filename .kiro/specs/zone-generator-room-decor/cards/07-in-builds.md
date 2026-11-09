# 7 — Decor in builds

Index entry: `tasks.md` task 7. Requirements 5.4, 8, 9.3, 9.5, 11.2, 11.3.

## Goal
Dungeon, city and outdoor-dungeon builds place Props: one `prop_<kind>_<variant>_<set>.mod` per kind in use, one ZON object per Prop, one ZON light per light-bearing Prop, the GLB `decor` mesh, the sidecar's `props`, `dressing` and `decor_drops`, and the gate on every build.

## Done when
- [ ] Builds pass the gate with Props; Decor `none` is step 10's bytes for every zone type; same inputs same `.eqg`.
      → verify: `python -m pytest tests/test_decor_builds.py tests/test_layout_engine.py -q`
- [ ] P8: one ZON light per light-bearing Prop; the room's own light stays.
      → verify: `python -m pytest tests/test_decor_builds.py -q -k light`
- [ ] Build time and the gate's first-try rate recorded in the commit body.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`pipeline.py` and `builder.py` are cross-branch hotspots: keep edits small. Packing follows the `site_` path.

## Result

