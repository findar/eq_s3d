# TASK: cave-backend-refactor

Status: absorbed        <!-- not-started | in-progress | blocked | done | absorbed -->
Absorbed by: M0 — the cave pipeline and theme were deleted outright; nothing to park or refactor (umbrella design, "Scope of open task files").
Epic: Cave rebuild ("cavify the dungeon layout") — part 1 of 2. Park the
      independent cave backend so it stops producing untrustworthy output, and
      isolate the cave-specific code behind a clean seam so the replacement
      (`cave-cavify-dungeon`) can slot in without fighting the old path.
Last touched: created alongside cave-cavify-dungeon, after the traversability
      validator landed (commit 7aa36ff)

## Goal

The current `cave` theme re-derives its own spatial structure (chambers from
rooms, tunnels from corridors, fragile endpoint matching) and renders as
disconnected solid blobs in 3D even though the connectivity tests pass — the
tests and the render disagree, so the backend builds geometry our analysis
doesn't faithfully capture (the "cave lesson" that motivated the whole
mesh-based validator). Per the standing ROADMAP decision ("Cave = cavified
dungeon layout"), we're not patching it further. This task **parks** that
backend and **refactors the cave-specific logic out of the hot path** so:

1. Nothing ships a cave zone through the broken independent derivation.
2. The cave-specific modules/wiring are isolated behind a single, documented
   seam (a geometry-backend interface or a clearly-quarantined module) so the
   replacement cavify pass (`tasks/cave-cavify-dungeon.md`) plugs in cleanly.

Done when the `cave` theme no longer routes to the old SDF-from-rooms backend
by default, the cave code is isolated (not deleted — kept for reference/reuse of
the SDF/feature primitives), the box/outdoor paths are untouched, and the suite
is green. This is deliberately a **no-new-capability** refactor: it removes a
trap and sets the table, it does not build the cavify pass.

## Why (and what NOT to do)

- Don't delete the SDF / marching-cubes / features primitives. The cavify
  rebuild will likely reuse `generators/field/sdf.py`, `mesh.py`, `noise.py`,
  and `features.py` (stalactites/stalagmites/pillars) — the problem was the
  *spatial derivation* (`_build_organic` turning rooms→spheres, corridors→
  capsules with centre-anchoring hacks), not the meshing primitives.
- Don't leave `cave` silently falling through to the box backend with no signal.
  A player asking for a cave and getting a box dungeon with cave textures is a
  different kind of wrong. Decide the interim behaviour explicitly (see
  Subtasks) and make it visible.
- Keep the seam honest: the whole point of the rebuild is that connectivity is
  established once, in the backend that gets it right. The refactor must not
  re-introduce a second source of truth for connectivity.

## Acceptance criteria

- [ ] The `cave` theme no longer routes to `_build_organic` (the rooms→spheres/
      corridors→capsules derivation) in the default generate path. Interim
      behaviour is explicit and documented (decision recorded below).
- [ ] Cave-specific logic is isolated behind one clear seam — either a
      `GeometryBackend` interface (box/terrain/cave as pluggable backends) or a
      single quarantined `generators/field/cave_legacy.py` — with
      `generators/builder.py` reduced to backend selection only. No cave
      internals leak into the generic build flow.
- [ ] SDF / mesh / noise / features primitives are preserved and still import
      cleanly (they're the raw material for the cavify pass), even if not wired
      into the default path.
- [ ] Box (dungeon/city) and outdoor paths are behaviourally unchanged —
      existing tests for those stay green with no edits.
- [ ] `tests/test_cave.py` is updated to match the new seam: tests that exercise
      the *primitives* (SDF carve, walkable floor, feature fusing, mesh
      round-trip) stay and pass; tests that assert the old rooms→cave *pipeline*
      are quarantined/xfail/removed with a note pointing at `cave-cavify-dungeon`.
- [ ] Full suite green (`python -m pytest tests/ -q`).
- [ ] Docs synced: ROADMAP "Cave = cavified dungeon layout" + Known issues +
      status table; README if it claims a working cave theme; this file.

## Subtasks

- [ ] **Decide the interim `cave` behaviour** (needs the user's call; options):
      (a) route `cave` to the box backend with cave textures/palette + a clear
      "cavify pending" flag in the response/CLI; (b) reject `cave` with a
      friendly "temporarily unavailable, use dungeon" error; (c) keep producing
      the old organic mesh but mark it experimental/opt-in (`--experimental-cave`).
      Record the decision here before implementing.
- [ ] Inventory the cave surface (done in investigation — keep current):
      - `generators/field/cave.py` — `CaveSpec`, `Chamber`, `Tunnel`, `build_cave`
        (the independent spatial derivation; the thing being parked).
      - `generators/field/features.py` — stalactite/stalagmite/pillar fusing (REUSE).
      - `generators/field/sdf.py`, `mesh.py`, `noise.py` — SDF/marching-cubes/noise
        primitives (REUSE).
      - `generators/builder.py` — `_CAVE_THEMES`, `_build_organic`,
        `_build_geometry` routing (the wiring to refactor).
      - `tests/test_cave.py` — split primitive tests (keep) from pipeline tests
        (quarantine).
      - Touch points that only name the theme (leave working): `main.py`
        choices, `server/app.py` VALID_THEMES, `ai/schema.py` VALID_THEMES,
        `analyzer/style_builder.py` cave reference zones, layout palette/light.
- [ ] Introduce the seam. Prefer a small `GeometryBackend` protocol
      (`build(spec, name, ter_version) -> TerFile`) with `BoxBackend`,
      `TerrainBackend`, and a parked `LegacyCaveBackend`; `builder._build_geometry`
      becomes a registry lookup. (If that's too big a change for one task, the
      minimum bar is moving the cave derivation out of `builder.py` into a
      clearly-named quarantined module and gating its selection.)
- [ ] Implement the chosen interim behaviour + make it visible (CLI note / API
      field / log line).
- [ ] Update `tests/test_cave.py` per the acceptance split; add a test that the
      default `cave` generate path does NOT invoke the legacy derivation.
- [ ] Full suite green; docs synced.

## Deliverables

- Code: `generators/builder.py` (routing/seam), possibly new
  `generators/backends.py` or `generators/field/cave_legacy.py`
- Tests: `tests/test_cave.py` (split), a guard test for the default cave path
- Docs: ROADMAP, README (if needed), this file
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Pairs with `tasks/cave-cavify-dungeon.md`.** This task parks + isolates;
  that task builds the replacement. Doing this one first keeps the rebuild from
  having to untangle the old wiring mid-flight. They could also be done together
  if the seam design falls out naturally from the rebuild — but the *parking*
  (stop shipping the broken path) is worth landing on its own, immediately.
- **Blocker:** interim `cave` behaviour (subtask 1) needs a user decision before
  implementing. Leaning toward (b) reject-with-friendly-error or (c)
  opt-in-experimental, so we never silently hand a player a box labelled "cave".
- Preserve determinism and the existing EQG/TER conventions (`ter_<name>.ter`).
- Standing lesson applies: structural-green is necessary-not-sufficient; whatever
  interim path we pick, don't let it claim "cave works" in 3D when it doesn't.
