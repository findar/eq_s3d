# TASK: cave-cavify-dungeon

Status: absorbed        <!-- not-started | in-progress | blocked | done | absorbed -->
Absorbed by: umbrella M5 — "cavify the dungeon layout" becomes the natural geometry style for any dungeon archetype (umbrella design, "Scope of open task files").
Epic: Cave rebuild ("cavify the dungeon layout") — part 2 of 2. Rebuild the
      `cave` theme as an organic-styling transform of the validated box/dungeon
      geometry, so connectivity is established once (by the backend that gets it
      right) and the cave is a styling pass over known-good geometry.
Last touched: created alongside cave-backend-refactor, after the traversability
      validator landed (commit 7aa36ff)

## Goal

Replace the parked cave backend with a **cavify pass**: generate the layout with
the box/dungeon backend (correct, connected, navigable rooms + corridors that
meet their openings — now provable with `analyzer/traverse.py`), then transform
that known-good geometry into an organic cave — round box rooms into irregular
chambers, convert corridors into winding tunnels, roughen walls with noise, fuse
in stalactites/stalagmites/pillars — **while preserving the connectivity that
already works**. Done when the `cave` theme produces a single connected,
navigable, organic-looking cave that passes the traversability validator (same
bar as dungeon) and reads as a natural cave in the 3D viewer, with the
disconnected-blob class of bug eliminated by construction.

## Why this architecture

The old backend re-derived spatial structure independently and rendered as
isolated blobs despite passing connectivity tests — tests and render disagreed.
The fix (long-standing ROADMAP decision "Cave = cavified dungeon layout") is to
stop re-deriving: the box backend already produces a connected, navigable graph
realised into geometry whose openings line up. Cavify styles THAT, so:

- Connectivity is a property of the input (the box layout), not something the
  cave pass has to rediscover. The disconnected-chamber bug can't recur if the
  transform preserves adjacency.
- We now have an objective gate: the **traversability validator** must pass on
  the cavified mesh with the SAME agent model as dungeon. That's the acceptance
  oracle the old backend never had.

## Open design question (decide early)

Two realisation strategies — pick with the user, record the call:

1. **Mesh-level deform** — take the box TER mesh and displace vertices with
   noise, bevel/round the hard edges, subdivide walls for relief. Closest to "a
   styling pass"; risk: keeping the mesh watertight + walkable floor intact
   while deforming, and corners/openings staying connected.
2. **Re-voxelise into an SDF and re-mesh** — rasterise the box rooms+corridors
   as solid, invert to an air-volume SDF, roughen the field with noise, fuse
   features, marching-cubes back to a TER. Closest to the current field
   primitives (`sdf.py`/`mesh.py`/`features.py`) and composes with the
   "terrain-as-SDF" / cave-mouth-in-hillside idea. Risk: voxel resolution vs.
   poly budget vs. preserving the navigable floor (the old backend lost floors
   to decimation — keep `decimate=None`, tune `voxel`).

Recommendation: **(2) SDF re-voxelise**, because it reuses the field primitives
the refactor preserved and because carving one connected air volume from the box
layout's union is exactly what makes "one connected cave" true by construction —
but the input air volume comes from the VALIDATED box layout, not from
rooms→spheres. The thing that was wrong before was deriving spheres/capsules
independently; here the SDF is rasterised directly from the box rooms/corridors
that already connect.

## Acceptance criteria

- [ ] `cave` theme generates by (box layout) → (cavify transform) → TER; no
      independent rooms→chambers/corridors→tunnels re-derivation.
- [ ] The cavified mesh PASSES `analyzer/traverse.py` (all rooms reachable) for a
      seed sweep — the same bar dungeon must meet. This is the headline gate.
- [ ] One connected cave: the walkable air volume is a single component
      (chambers joined by tunnels), not separate bubbles — asserted
      programmatically (component count == 1) AND confirmed in 3D.
- [ ] Reads as a natural cave (`docs/ACCEPTANCE.md` section D): irregular organic
      chambers (not perfect spheres), winding tunnels, hand-sculpted wall relief
      at EQ resolution, stalactites/stalagmites/pillars fused (not glued-on).
- [ ] Watertight / no see-through / no floating specks (ACCEPTANCE section C) —
      the floor renders solid from above; no stray blobs.
- [ ] Navigable floor preserved: walkable-floor % stays above the existing
      `tests/test_cave.py` bar; corridors-as-tunnels remain walkable (no cliff
      ramps / oversized drops introduced by the transform — re-check with the
      validator's agent model).
- [ ] Seed-sweep pytest (extend `tests/test_cave.py` or add
      `tests/test_cavify.py`): connectivity == 1 component, watertight, and FULL
      traversability for several cave seeds.
- [ ] Human 3D eyeball on several seeds (per the cave lesson): tests-green is
      necessary-not-sufficient. Log the pass here.
- [ ] Docs synced: ROADMAP (cave moves from shelved → done; status table),
      README (cave theme trustworthy again), `docs/ACCEPTANCE.md` section D
      confirmed, this file.

## Subtasks

- [ ] Decide realisation strategy (mesh-deform vs SDF re-voxelise) with the user;
      record the call + rationale here.
- [ ] Build the cavify transform: input = the box backend's TER (or its
      rooms/corridors rasterised); output = organic TER. Reuse the preserved
      field primitives (`sdf.py`, `mesh.py`, `noise.py`, `features.py`) rather
      than the parked spatial derivation.
- [ ] Wire it into the geometry-backend seam from `cave-backend-refactor` so
      `cave` selects the cavify backend; flip the interim behaviour off.
- [ ] Preserve the navigable floor and openings through the transform; tune
      voxel/noise so chambers read organic without sealing tunnels or pitting
      floors.
- [ ] Run the traversability validator in the loop while tuning (it's the
      objective gate); add the cave seed sweep to the suite.
- [ ] Full suite green + 3D eyeball pass on several seeds; log results.
- [ ] Docs: promote cave from shelved to working; sync ROADMAP/README/
      ACCEPTANCE; this file.

## Deliverables

- Code: a cavify backend (e.g. `generators/field/cavify.py`) wired through the
  geometry-backend seam; reuses `sdf.py`/`mesh.py`/`noise.py`/`features.py`
- Tests: `tests/test_cave.py` (extended) or `tests/test_cavify.py` — connectivity,
  watertight, full traversability sweep
- Docs: ROADMAP (cave done), README, `docs/ACCEPTANCE.md` section D; this file
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Depends on `tasks/cave-backend-refactor.md`** (the seam + parking). Start
  after — or alongside if the seam design falls out of the rebuild naturally.
- **The traversability validator is the objective gate this task finally gives
  the cave backend.** The old backend's fatal flaw was passing structural tests
  while rendering broken; now the cavified mesh must pass the same mesh-walk the
  dungeon does. If the validator's outdoor/cave coordinate-frame limitation
  (ROADMAP Known issue) is still open, confirm the cavified cave shares the box
  layout's coordinate frame (it should, since it's derived from the box geometry)
  so the validator applies directly — this rebuild may well resolve that limit
  for caves for free.
- Keep determinism (seed → same cave) and EQG/TER conventions (`ter_<name>.ter`,
  per-triangle collision — the mesh IS the collision model).
- Scope guard: this is geometry/navigability + "reads as a cave". NOT the
  content/semantic layer for caves, NOT cave-mouth-in-hillside composition (that's
  the separate water/mixed-environment work) — though SDF re-voxelise is chosen
  partly because it composes toward that later.
