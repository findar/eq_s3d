# 6 — GLB `vegetation` node

Index entry: `tasks.md` task 6. Design: "Build integration" (`core/eqg.py`).
Requirement 9.1.

## Goal
The GLB preview of a wilderness build with trees is a scene with a `terrain`
node and a `vegetation` node; every other GLB is byte-identical to today.

## Done when
- [ ] `write_glb` takes optional extra meshes; with none, output bytes are
      unchanged (test on a dungeon and a `none` wilderness).
- [ ] The `vegetation` node holds every Tree_Instance, transformed by its yaw,
      scale and position, coloured by the Species' bark and leaf colours.
- [ ] A loaded GLB has exactly those two node names.
      → verify: `python -m pytest tests/test_wilderness_trees.py -q`.

## Pitfalls
- Merge all instances into one mesh per node; one node per tree would make a
  slow viewer.
- lessons-learned: the GLB uses base colours, not DDS textures.

## Result
