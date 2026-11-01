# 4 — Textured GLB terrain

Index entry: `tasks.md` task 4. Design: "Preview". Requirements 6.1–6.3.

## Goal
The GLB `terrain` node draws each material with its packed diffuse and the
TER's UVs; without textures the GLB is byte-identical to before.

## Done when
- [x] Probe which way EQ's V axis runs against glTF's, using a texture whose
      orientation is known (our own label textures), record it in the commit
      body, and apply the flip if needed.
- [x] X7 holds for dungeon, city and wilderness builds.
- [x] A material whose texture can't be decoded falls back to base colour with
      a `texture_preview_fallback:<name>` warning; the build still writes.
- [x] A `write_glb` call without `textures` is byte-identical to master.
      → verify: `python -m pytest tests/test_glb_textures.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Keep one `terrain` node; the viewer frames on it (step 2 task 9).
- The `vegetation` node stays base-coloured.
- trimesh embeds images through Pillow, which `requirements.txt` already pins.

## Result
✔ 448cd04 · 725 passed
