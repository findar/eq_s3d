# 7 — Texel density from the profile

Index entry: `tasks.md` task 7. Design: "Texel density". Requirement 6.

## Goal
Box-backend UVs repeat at the theme's measured Texel_Density p50 per surface
in `procedural` and `ai` modes, and at step 3's 100 u in `placeholder` mode,
keeping step 3's orientation rules. Wilderness UVs are untouched.

## Done when
- [ ] Y6: on dungeon and city builds each surface's world units per repeat
      equals the target density for the mode (wilderness unchanged); walls
      still run `v` down and `u` right from inside, floors `v = −y`, ceilings
      `v = +y`.
- [ ] X3's UV-free geometry goldens pass untouched.
      → verify: `python -m pytest tests/test_texel_density.py tests/test_wall_uvs.py tests/test_material_names.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- `add_quad` takes `uv_scale`; thread the density through, don't hard-code it.
- The builder decides the mode before geometry; pass the scale down rather
  than having geometry read the environment.

## Result
