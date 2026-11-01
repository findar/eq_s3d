# 3 — Procedural tree models and leaf/bark textures

Index entry: `tasks.md` task 3. Design: "Tree models". Requirement 2.

## Goal
`tree_model(species, seed)` builds a low-poly `EQGM` TerFile per Species, with a
solid buried trunk and a walk-through, double-sided canopy of cards. The leaf
texture has a real alpha silhouette.

## Done when
- [x] Property T1 holds on 200 examples (any Species the kit schema allows, any
      seed): 24–96 triangles, ≥ 1 trunk triangle with flag `0x01` clear, ≥ 1
      canopy triangle with it set, trunk min z ≤ −2, round trip through
      `core.ter` identical.
- [x] Canopy material uses `SHADER_CHROMA` and `veg_<species>_leaf.dds`; trunk
      uses `SHADER_OPAQUE` and `veg_<species>_bark.dds`.
- [x] `leaf_texture` returns a DDS whose alpha has both 0 and 255 texels and
      whose silhouette is rounded (broadleaf) or triangular (conifer).
- [x] Every canopy card has both windings (double-sided), and face normals are
      unit length.
      → verify: `python -m pytest tests/test_vegetation_models.py -q`.

## Pitfalls
- Z is up; the model origin is ground level.
- `core.ter` writes the extra `bone_count` for `EQGM`; use `MAGIC_MODEL`.
- Umbrella Req 32.7: no mesh file as input, not even as a template.

## Result
✔ 7511f90 · 606 passed · plains models 32/40/32 tris · not checked in 3D
