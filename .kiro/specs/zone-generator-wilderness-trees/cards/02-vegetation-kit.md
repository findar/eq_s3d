# 2 — Vegetation kit data and loader

Index entry: `tasks.md` task 2. Design: "Vegetation kit". Requirement 1.

## Goal
`styles/vegetation.json` holds the `plains_grassland` kit, and
`generators/vegetation/kit.py` loads and validates it by the biome's
`vegetation_kit` id.

## Done when
- [ ] `load_vegetation_kit(kit_id)` returns a typed kit: Species (form, weight,
      height, canopy, trunk_radius, scale, bark and leaf colours), density per
      level, grove parameters. A missing id returns `None`; a malformed entry
      raises naming the field.
- [ ] `plains_grassland` has broadleaf, conifer and sapling, with heights inside
      46–130 u at scale 1 (Req 1.2).
- [ ] The id in `styles/biomes.json` (`plains_grassland`) resolves.
      → verify: `python -m pytest tests/test_vegetation_kit.py -q`.

## Pitfalls
- Follow `generators/wilderness/biome.py`'s style for the loader and its
  validation; don't add the kit to `biomes.json` itself.

## Result
