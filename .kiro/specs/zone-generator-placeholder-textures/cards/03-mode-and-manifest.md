# 3 — Texture mode and texture manifest

Index entry: `tasks.md` task 3. Design: "Provider and manifest".
Requirements 4, 5.

## Goal
The default Texture_Mode is the one `archive.md` records, `EQ_S3D_TEXTURE_PROVIDER`
picks any of the three, the builder passes each material's Surface_Class, and
the sidecar carries the Texture_Manifest.

## Done when
- [ ] With no override, every build's room-graph and wilderness textures are
      drawn in the default mode; `placeholder`, `procedural` and `ai` all
      work by override (`ai` falls back).
- [ ] X6 holds for dungeon, city and wilderness builds (tree materials
      included), and each entry records its Texture_Mode.
      → verify: `python -m pytest tests/test_texture_manifest.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Tests that assert procedural texture bytes or the provider seam may need the
  override; check `tests/test_wilderness_biome_kit.py` and the texture tests.
  If a test outside `Owns` breaks, stop and ask.
- Tree textures stay on their own path; list them in the manifest only.

## Result
