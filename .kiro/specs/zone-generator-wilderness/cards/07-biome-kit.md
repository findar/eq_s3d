# 7 — Plains biome kit and ground textures

Index entry: `tasks.md` task 7. Old task 12.3. Requirements 11.1–11.3.

## Goal
Give the Karana its plains identity. Add a data table (not code per biome)
that, for each biome, names the ground textures, the sky/fog tint and a
vegetation-kit id. Apply the `plains` entry over the shared terrain core, so
the ground is textured by slope, height and moisture instead of flat colours.

## Done when
- [ ] The `BiomeKit` table is a JSON data file (`styles/biomes.json` or
      `biomes/plains.json`) with a `plains` entry. Adding a biome means adding
      data, not a generator.
      → verify: `tests/test_wilderness_biome_kit.py` loads the table and the `plains` kit resolves.
- [ ] Wilderness TER materials come from the kit. The ground blends between ≥ 2
      textures by slope/height, and textures go through the existing
      `generators/textures/factory.py` seam (procedural by default, with no API key).
      → verify: test that forces a provider through the seam and asserts the call path.
- [ ] The TER has real UVs. `build_bowl_ter` currently writes `u=v=0`.
      → verify: test that the UVs are not all zero.
- [ ] **Vegetation decision recorded:** v1 carries only the kit's vegetation
      *id* (trees are roadmap step 2). Note it in `archive.md` "Decisions".
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- The GLB preview uses per-material base colours, not real DDS textures
  (lessons-learned, Web viewer). Give each kit material a sensible base colour,
  or the preview gets worse than task 2's flat colours.

## Result
✔ c02a1a2 · 509 passed
