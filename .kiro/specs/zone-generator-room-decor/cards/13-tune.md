# 13 — Tune from the first look

Index entry: `tasks.md` task 13.

## Goal
Act on the first look's findings: counts, Sets, placement, and tag corrections the user names.

## The first look's findings (task 12, 2026-11-10)
1. **Banners aren't visible** in the viewer. Builds do place them (e.g. 4 MISTBANNER wall
   Props in a dense dungeon, sidecar rows present). Find where they vanish: the frozen
   vertex-animated import (decision 24), a masked/alpha texture whose mean colour is
   transparent in the GLB `decor` mesh, facing (a one-sided quad seen from behind), or a
   position off the wall. Fix so they show in the viewer and the client.
2. **Torches don't know where to mount against a wall.** Wall Props keep stock's origin and
   face the wall's into-room normal with the model's front assumed +X (decision 21); only
   TORCHPOINT was checked. Measure from stock placements which side of each wall model faces
   its wall and how far its origin stands off it, store it per model in the catalogue, and
   place wall Props flush to the actual wall mesh (rough walls: sample the mesh, design Risks).
3. **A box below the world** (the user's screenshot: an open crate fully under the floor).
   Leads from built zones: a floor Prop at z = 0 in a room whose floor is ~102 (HAVRUBBLE301,
   zone seed 2112160981) suggests a floor-height lookup falling back to 0; crates and barrels
   in a dense dungeon sit 0.7–1.2 u under the lowest nearby floor vertex. Floor and raised
   Props must stand on the floor under their footprint, never below it.

Diagnostic used: the lead's `s11_look.py` (scratchpad) reads a built `.eqg` + sidecar and
lists wall Props and floor Props below the nearest floor.

## Done when
- [x] A test pins each finding: no floor/raised Prop below the floor under it; every wall Prop's back within 1 u of the wall mesh; banners present in the GLB `decor` mesh with visible (non-zero alpha) faces.
      → verify: `python -m pytest tests/test_decor_builds.py tests/test_decor_placement.py -q`
- [x] Each finding from task 12 is fixed or recorded as a follow-up in `archive.md`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Change values and placement, not the gate.

## Result
✔ 0ac6dfe · 2365 passed
