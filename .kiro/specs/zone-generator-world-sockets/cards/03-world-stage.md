# 3 — The World stage

Index entry: `tasks.md` task 3. Requirements 1.2, 1.3, 2.1–2.3. Design "The World", "The Socket", "Today's pipeline".

## Goal
`world_for(zone_type, seed, *, biome, edges, zone_size, landform)` and `world_of(spec)` (from a spec's `wilderness` payload and seed) return the design's World: the terrain from `synthesize_landscape` (heights exactly as `build_wilderness_ter` writes the TER's grid vertices, so after the water bed sinks), cell types, Rim seal and playable-interior masks, water level, regions, the Spawn, and the Sockets each zone type offers. A dungeon or city gets no terrain and one `root` Socket; a wilderness one `ground`; an outdoor dungeon one `hillside` (footprint clipped to the bowl's interior, the undiggable cells, the approach foot with its ground height and side, the Rock_Cover, the grid's origin and resolution) and one `ground`. Nothing calls them yet; no build changes.

## Done when
- [ ] P2 and P3: `world_for` takes no room, Site or Decor input; the same inputs give the same text; each zone type offers its Sockets.
      → verify: `python -m pytest tests/test_world.py -q`
- [ ] The World's height grid equals the built TER's grid vertex Zs, exactly, for a wilderness and an outdoor dungeon's host; the hillside's entry height equals what `host_envelope` reads at the foot.
      → verify: `python -m pytest tests/test_world.py -q -k exact`
- [ ] Bytes unchanged.
      → verify: `python -m pytest tests/test_layout_engine.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
The entry height comes from `ter_surface` interpolated at the foot: compute it the same way on the same grid. `keep_clear_shapes` reads `land.bowl.heights` (before the water bed sinks) while the Entrance reads the TER grid (after): carry both if both are needed, or show they agree where the Apron digs. The payload records the PLACED Landform, not the request. Add functions only; `outdoor_dungeon_spec` changes in task 4.

## Result
