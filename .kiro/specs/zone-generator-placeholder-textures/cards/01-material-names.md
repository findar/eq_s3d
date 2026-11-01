# 1 — Material names by set and surface; real shaders

Index entry: `tasks.md` task 1. Design: "Names". Requirements 1, 2, 7.1.

## Goal
Dungeon and city materials are named `<Texture_Set>_<Surface>` and use
`Opaque_MaxCB1.fx`; nothing else about the build changes.

## Done when
- [ ] First commit, on unchanged code: a golden test of TER vertex and polygon
      hashes (vertices, and each polygon's v1/v2/v3/flags/material, names
      excluded) for pinned dungeon, city and wilderness seeds. It passes.
- [ ] After the rename the same golden test passes untouched (X3), and X1, X2
      and X4 hold for dungeon (plain and themed, with and without a race,
      with a tint), city and wilderness builds.
      → verify: `python -m pytest tests/test_material_names.py tests/test_rof2check.py -q`.
- [ ] The format gate rejects `<fixed-function>`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Race `default` means no race.
- Other tests may look materials up by the bare names `floor`/`wall`/`ceiling`
  (grep `tests/`). If one outside `Owns` breaks, stop and ask before widening.
- `tests/test_rof2check.py`'s property corruptions build dungeons; keep the
  check list unchanged.

## Result
