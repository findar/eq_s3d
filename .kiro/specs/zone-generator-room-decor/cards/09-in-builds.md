# 9 — Decor in builds

Index entry: `tasks.md` task 9. Requirements 6.4, 9, 10.3, 10.5, 10.6, 12.2, 12.3.

## Goal
Dungeon, city and outdoor-dungeon builds place Props: each model in use imported once and packed, one ZON object per Prop, one ZON light per light-bearing Prop, the GLB `decor` mesh, the sidecar's `props`, `dressing` and `decor_drops`, the gate on every build (P13: decor's own room check agrees with it on these builds), contexts built by `room_context.contexts`, and Decor `none` with a warning when the install is missing.

## Done when
- [ ] Builds pass the gate with Props; Decor `none` is step 10's bytes for every zone type; same inputs same `.eqg`.
      → verify: `python -m pytest tests/test_decor_builds.py tests/test_layout_engine.py -q`
- [ ] P9: one ZON light per light-bearing Prop; the room's own light stays.
      → verify: `python -m pytest tests/test_decor_builds.py -q -k light`
- [ ] Build time and the gate's first-try rate recorded in the commit body.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`pipeline.py` and `builder.py` are cross-branch hotspots: keep edits small. Packing follows the `site_` path.

## Result
✔ acc21e3 · 2289 passed
