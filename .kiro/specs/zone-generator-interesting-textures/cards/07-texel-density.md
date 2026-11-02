# 7 — Texel density from the profile

Index entry: `tasks.md` task 7. Design: "Texel density". Requirement 6.

## Goal
Box-backend and wilderness UVs repeat at the theme's measured Texel_Density per
surface (as Open question 1 decides), keeping step 3's orientation rules.

## Done when
- [ ] Y6: on dungeon, city and wilderness builds each surface's world units per
      repeat equals the target density; walls still run `v` down and `u` right
      from inside, floors `v = −y`, ceilings `v = +y`.
- [ ] X3's UV-free geometry goldens pass untouched.
      → verify: `python -m pytest tests/test_texel_density.py tests/test_wall_uvs.py tests/test_material_names.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- `add_quad` takes `uv_scale`; thread the density through, don't hard-code it.
- Find where wilderness ground UVs are set before starting, and name the file
  in the first commit.

## Result
