# 7 — Sites in builds

Index entry: `tasks.md` task 7. Requirements 4.4, 7, 8.2, 8.4, 9.2, 9.3.

## Goal
Wilderness and outdoor-dungeon builds place Sites: one `site_<kind>.mod` per kind and variant, one ZON object per Structure, the Footprint gate on every build, the sidecar `sites` block. Outdoor dungeons keep the Apron, Tunnel, Mouth and Host_Hill clear.

## Done when
- [ ] Builds pass the gate with Sites; `none` is step 9's bytes; dungeon and city goldens unchanged; same inputs same `.eqg`.
      → verify: `python -m pytest tests/test_site_builds.py tests/test_layout_engine.py tests/test_topology_levels.py -q`
- [ ] P8: outdoor dungeons hold step 5's guarantees.
      → verify: `python -m pytest tests/test_site_builds.py -q -k outdoor`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`generators/pipeline.py` and `builder.py` are cross-branch hotspots: keep edits small. Packing follows the `veg_` path in `builder.py`.

## Result
✔ 2fabea3 · 2049 passed
