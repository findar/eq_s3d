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
- EQG collision is per-triangle, from the polygon `0x01` flag
  (lessons-learned, File formats). Water polygons without that flag are visual only.
- Extend `generators/wilderness/build.py` (from task 2), not `backends.py`.
- Real swimmable or shallow-water volumes are out of scope; say so in a code
  comment.

## Result
<!-- worker: one line -->
