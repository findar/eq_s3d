# 6 — Visual water plane

Index entry: `tasks.md` task 6. Old task 12.4. Requirements 11.4, 13.1.

## Goal
River edges and interior water currently show up as bare channels. Add a flat
water surface at the zone's water level that you can see but that has **no
collision**. Edges are already sealed by the Invisible_Wall, so the water is
purely visual.

## Done when
- [ ] A build whose matrix has `water` cells contains a flat water surface at
      `water_level`, using its own `water` material, with a
      `RegionSpec(kind="water")` (→ `AWT`).
      → verify: test in `tests/test_wilderness_water.py`.
- [ ] The water polygons are **not collidable**, so `check_bowl` and the
      walk surface ignore them.
      → verify: Property 15 is still green; test that no water polygon carries the collision flag.
- [ ] `ZoneSpec` carries `water_level` (defaulted; absent from dungeon/city
      `to_dict()`).
- [ ] The water shows in the `.glb` preview (its own colour).
- [ ] `python -m pytest tests/ -q` is green.

## Hints
- EQG collision is per-triangle: `core/ter.py` `FLAG_PASSABLE = 0x01` marks a
  polygon NON-collidable, so the water polygons carry `flags=FLAG_PASSABLE`.
  Every existing mesh uses `flags=0` (solid).
- `analyzer/traverse.build_walk_surface` ignores polygon flags today, so the
  agent would stand on the water plane. Teach it to skip `FLAG_PASSABLE` faces
  (defaulted, so no dungeon/city result changes) or Property 15 becomes
  meaningless for river edges. This adds `analyzer/traverse.py` to Owns.
- Extend `generators/wilderness/build.py` (from task 2), not `backends.py`.
- Real swimmable or shallow-water volumes are out of scope; say so in a code
  comment.

## Result
✔ aa6cb0a · 499 passed (surface material is `liquid_water` for rof2check; not eyeballed in 3D)
