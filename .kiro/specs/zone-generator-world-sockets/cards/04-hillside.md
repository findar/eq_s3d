# 4 — The outdoor dungeon attaches to its hillside Socket

Index entry: `tasks.md` task 4. Requirements 2.4, 3.1, 3.5, 6.1. Design "The Attach stage", "Order and Terrain edits", "Risks". Written for the recommended answer to design question 1 (the Socket fixes the hill; the Attach stage picks the Mouth).

## Goal
`host_envelope`, `plan_dungeon`, `align_to_grid`, `plan_entrance` and `_apron` read a `hillside` Socket and the World's terrain instead of `(host spec, TER)`. `outdoor_dungeon_spec` makes the World with `world_for`, attaches the dungeon through `generators/stages.py` (`attach_rooms(world, socket, fields, seed, engine)`), and no longer builds a TER to plan. The Envelope's floor limit comes from the dungeon's own verticality and race. The Apron becomes a Terrain edit (the dug grid and the Spawn's new height), applied by one function, `stages.apply_edits(world, attachments)`, which the build uses from task 5 on. A Socket that can't take the dungeon raises one of `PLAN_ERRORS`, naming the Socket. Every outdoor dungeon keeps its bytes.

## Done when
- [ ] Bytes unchanged, and the outdoor-dungeon tests pass.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_outdoor_dungeon_build.py tests/test_outdoor_levels.py tests/test_outdoor_walls.py -q`
- [ ] P5 and P10: attaching from a World builds no TER and never calls `synthesize_landscape` (patched to raise in the test); the rooms lie in the Envelope, the Tunnel is covered and within grade, the Apron digs no undiggable cell.
      → verify: `python -m pytest tests/test_attach_hillside.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Design Risks "Hidden reads": every `landscape_for(host)` in the planner (grid, resolution, cell types, bowl interior, Landform) must go through the Socket, `keep_clear_shapes` included. Exact floats: a rounded height moves a room. `ai/expand.py` is a hotspot: touch only the outdoor-dungeon branch. The Spawn's drop belongs to the Terrain edit, not to `plan_to_spec`.

## Result
