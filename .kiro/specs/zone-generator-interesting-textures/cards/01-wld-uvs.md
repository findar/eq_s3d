# 1 — WLD reader keeps UVs and polygon textures

Index entry: `tasks.md` task 1. Design: "Reader". Requirement 1.

## Goal
`WldMesh` carries each vertex's texture coordinates and each polygon's texture
index, so classic texel density can be measured.

## Done when
- [ ] `uvs` (old format int16 / 256, new int32 / 256) and `polygon_textures`
      (expanded from the polygon-texture groups) are filled for 0x36 meshes.
- [ ] Y1: on befallen, unrest, najena, mistmoore and qeynos2 the texcoord count
      equals the vertex count and the per-zone wall median matches the design's
      research table within 0.5 u (skip when `EQ_PATH` is unset).
- [ ] Existing callers see the same vertices, polygons and texture names.
      → verify: `python -m pytest tests/test_wld.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- lessons-learned "WLD specifics" (magic, old-format flag, XOR key).
- The polygon-texture groups come after the vertex pieces; count both.

## Result
