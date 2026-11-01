# 5 — Build integration: archive, ZON objects, sidecar, gate

Index entry: `tasks.md` task 5. Design: "Build integration", "Walkability".
Requirements 6, 7, 8.1–8.2, 9.3, 10, 11.

## Goal
A wilderness build packs the tree models and textures, places one ZON object per
tree, writes the sidecar `vegetation` block, and fails the gate if trunks cut
off any playable cell. Dungeon and city builds don't change.

## Done when
- [x] `vegetation_for(spec, ter)` is pure and cached; the builder and
      `bowl_report` share it.
- [x] Properties T5–T9 hold (TER identical across levels; trunk walkability;
      ZON/archive consistency; `none` and room-graph builds have no `.mod` and
      no objects, room-graph EQG bytes unchanged; byte-identical repeat builds).
- [x] A test removes the clearance rule on purpose and shows the gate rejects a
      blocking placement (the check isn't vacuous).
      → verify: `python -m pytest tests/test_wilderness_trees.py -q`.
- [x] `python -m pytest tests/ -q` is green.
      → verify: `python -m pytest tests/ -q`.

## Pitfalls
- `generators/builder.py` is a cross-branch hotspot; keep the edit small.
- The default level is `normal`; read it from `spec.wilderness.get("trees",
  "normal")` so task 8 only has to set it.
- lessons-learned: "Automated structural tests can pass while the 3D viewer
  shows it's broken". The GLB node is task 6; say "not checked in 3D".

## Result
✔ 28f962a, ea94906 · 623 passed · byte-identity excludes the PFS footer timestamp · not checked in 3D
