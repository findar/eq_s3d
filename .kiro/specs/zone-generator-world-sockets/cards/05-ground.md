# 5 — Sites attach to the ground Socket

Index entry: `tasks.md` task 5. Requirements 3.2, 3.3, 6.1. Design "The Attach stage", "Order and Terrain edits". Written for the recommended answer to design question 2 (an area Socket).

## Goal
`place_sites` takes the World's terrain (with earlier Attachments' edits applied) and the `ground` Socket (Spawn, Kept_Clear shapes) instead of `(land, ter)`; `vegetation.placement.ground_for` gets a World form. `sites_for` builds the World (`world_of(spec)`), applies the spec's Entrance through `stages.apply_edits`, and attaches the ground Socket through `stages.attach_sites`. The Sites' stream is salted from one named seed in `stages.py`, the zone seed until task 7 makes it `rooms_seed`. Every build with Sites keeps its bytes; trees are unchanged.

## Done when
- [x] Bytes unchanged; Site, decor and tree builds pass.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_site_decor_builds.py tests/test_wilderness_trees.py -q`
- [x] P6: on an outdoor-dungeon World, the ground Attachment sees the Apron's heights and the hill, Tunnel and Apron as Kept_Clear, and gives the same Sites as `sites_for` on the built TER.
      → verify: `python -m pytest tests/test_attach_ground.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
`ground_for` reads the TER's first `nx * ny` vertex Zs; on an outdoor dungeon those already hold the dug Apron, so World plus edit must give the same floats. Trees share `ground_for`: don't change what they get. The `lru_cache`s key on the TER's fingerprint; key them on the World's inputs and edits instead, kept as small.

## Result
✔ 93919a8 · 2414 passed
