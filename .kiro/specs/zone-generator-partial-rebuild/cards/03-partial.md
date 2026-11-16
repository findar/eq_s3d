# 3 — Rebuild from the saved stages

Index entry: `tasks.md` task 3. Requirements 2.2, 2.3, 4.1. Design "Rebuild" (Partial), "Proof";
decision 2.

## Goal
`generators/rebuild.py` `rebuild_decor(parent_dir, changes, ...)`: load the parent's spec and
decor layers, apply a new `decor_seed` (clearing `room_decor_seeds`) or one `room_decor` entry,
and build with the parent's TER and textures taken from its `.eqg` (a seam in `ZoneBuilder.build`;
geometry and texture drawing skipped), the full gate still, then format check, map files and
finalize into `v<n+1>` with `how: "partial"`. `/api/rebuild` takes `room_decor: {room,
decor_seed}` and sends decor changes here; `rooms_seed` stays full. Measure each zone type's
partial rebuild against a full one (warm, median of 5) and put the numbers in the commit body.

## Done when
- [ ] A partial rebuild's `.eqg` equals a full Generate of the same request and seeds (footer
      aside), and its sidecar too but for `version` and timings: the 16-room Graph dungeon
      seed 2, a city, an outdoor dungeon, a Theme Tomb, a wilderness with Sites; each with a new
      decor seed and with one room decor seed. → verify: `python -m pytest tests/test_partial_rebuild.py -q`
- [ ] Bytes unchanged otherwise. → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_site_decor_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
The textures are drawn from seeds and Texture_Mode: reusing the parent's DDS must give the same
bytes the build would draw (it should; prove it rather than assume). Decor's own textures and
models still come from the install. A gate failure on a pinned decor seed is reported, never
rerolled.

## Result
