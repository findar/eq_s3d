# TASK: traversability-validator

Status: done        <!-- not-started | in-progress | blocked | done -->
Epic: Validation tooling (serves the "navigable" north-star; reduces manual UAT)
Last touched: validator built (dungeon/box backend); suite green, 3 known-bad xfail

## Goal

Build an automated validator that answers "can a player actually walk to every
room in this zone?" so navigability stops depending on a human walking each
generated zone in the viewer. It loads a generated zone's real geometry, models
an EQ-scale agent walking on walkable surfaces (bounded slope + step height),
flood-fills what's reachable from the entrance/safe point, and reports any room
whose floor can't be reached — plus *why* (cliff ramp, oversized step,
disconnected corridor, sealed room, floating geometry). Done when it reliably
flags the known-bad seeds we found by eye and passes known-good ones, is
runnable as a CLI and as a seed-sweep test, and is trustworthy enough to carry
the `docs/ACCEPTANCE.md` section B (Navigability) MUSTs instead of a human.

## Why (and the trap to avoid)

Navigability is a core goal, and today it's validated almost entirely by hand.
Every corridor bug so far (seeds 481893615, 1516796975, 1955208177 — misaligned
stairs, same-axis mis-connection, cliff ramps / 15u steps) **passed the existing
structural tests** and was only caught in the 3D viewer. So:

- The validator MUST operate on the **actual generated mesh** (the TER that
  ships), not just the room graph — the cave lesson is that the graph/analysis
  can say "connected" while the render is broken. The room graph is used only to
  know what SHOULD be reachable (every room's floor), not as the reachability
  proof itself.
- It MUST model real walking: a surface is standable if its slope is within a
  walkable cap; two standable surfaces connect if an agent can step between them
  within a max step-up height and they're horizontally adjacent. This is what
  catches cliff ramps and oversized stair steps — the exact failures the
  component-count checks miss.

It does NOT replace the *visual/aesthetic* eyeball (does the zone read as a
place, palette, lighting mood) — only the mechanical navigability MUSTs.

## Acceptance criteria

- [x] Loads a generated zone (`.eqg`/TER, via the existing `core` readers) and
      an agent model (EQ scale: height ~6u, walkable slope cap 40°, max step-up
      3u), and produces a pass/fail + per-room reachability report from the safe
      point / entrance.
- [x] Correctly FAILS the known-bad seeds (1955208177, 1516796975, 481893615)
      and names the offending corridor/room and the reason. The 53° cliff ramp
      and ~15u-step stairs are both reported as non-traversable (verified by
      `classify_corridor` unit tests + the live seeds, which the current layout
      realises as oversized-step stairs / misaligned corridors).
- [x] Correctly PASSES known-good flat zones (dungeon seeds 1, 6, 26, 49) — no
      false alarms.
- [x] Runnable as a CLI: `python -m analyzer.traverse output/<zone>.eqg`
      (also accepts a bare zone name under `--output`) with a readable report;
      exits non-zero on FAIL.
- [x] Backed by `tests/test_traversability.py`: sweeps known-good dungeon seeds
      (full reachability asserted) + unit tests for the agent/corridor classifier;
      the known-bad seeds are `xfail` until `corridor-connection` lands.
- [x] Documented: `docs/ACCEPTANCE.md` section B updated (which MUSTs are now
      auto for dungeon vs. still-manual outdoor/cave + aesthetic); ROADMAP synced.

## Subtasks

- [x] Decide the agent model + thresholds. **Numbers + rationale:** walkable
      slope cap **40°** (tan ≈ 0.84), matching the dungeon/cave terrain backend's
      `max_walkable_grad = 0.85` (`generators/builder.py`); max step-up **3.0u**
      (EQ player ~6u tall, so half-height is a generous-but-honest climbable gap
      — a ~7u stair step is borderline, a 15u step plainly impassable);
      adjacency XY tolerance **2u** for mesh-seam joins. Encoded in
      `AgentModel` with those as defaults/CLI flags.
- [x] Surface extraction: `build_walk_surface` classifies standable faces by
      `|normal.z| >= cos(slope_cap)` and builds adjacency two ways — shared-vertex
      (exact mesh connectivity) and XY-footprint proximity via a spatial hash
      (for corridor↔room seams where verts don't coincide) — each gated by the
      step-up height.
- [x] Reachability flood-fill (`flood_reachable`) from the safe-point's start
      face; `_faces_in_room` maps each room's footprint (XY-first, Z to
      disambiguate stacked floors) to the reachable set; `_diagnose_via_graph` +
      `_diagnose_unreachable` report unreachable rooms with the likely cause
      (cliff ramp / oversized step / misaligned-detached corridor / plain gap).
- [x] CLI entry point: clear report (PASS/FAIL, mesh stats, reachable N/total,
      per-room OK/XX with reason + offending corridor id).
- [x] Seed-sweep pytest `tests/test_traversability.py`: known-good dungeon seeds
      asserted fully reachable; known-bad seeds `xfail` until `corridor-connection`.
- [x] Validated the validator: FAILS 1955208177/1516796975/481893615 with named
      causes, PASSES flat seeds; classifier unit-tested against the exact 53°
      ramp / 15u step. **Still open: 3D viewer spot-check by the user** (see
      Notes — one human eyeball to fully trust it per the standing lesson).
- [x] Wired into `docs/ACCEPTANCE.md` (section B automated-vs-manual split) and
      noted in ROADMAP (item marked done + new Known-issue for the outdoor/cave
      coordinate-frame mismatch).

## Deliverables

- Code: `analyzer/traverse.py` — `AgentModel`, `load_ter_from_eqg`,
  `build_walk_surface`, `flood_reachable`, `classify_corridor`, `validate`,
  `TraversalReport`, and a `python -m analyzer.traverse` CLI.
- Tests: `tests/test_traversability.py` (13 pass + 3 xfail; runs in ~1.3s).
- Docs: `docs/ACCEPTANCE.md` (section B automated-vs-manual split), `ROADMAP.md`
  (item done + outdoor/cave coordinate-frame Known issue); this file.
- Verification: full suite green — `179 passed, 3 xfailed`.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- Strong synergy with `tasks/corridor-connection.md`: this validator is the
  automated gate that proves those fixes work (and guards against regressions).
  Reasonable to build the validator FIRST so it objectively measures the
  corridor fixes — or alongside. If built first, the known-bad seeds stay
  failing/xfail until corridor-connection lands.
- Keep it on the actual mesh (ground truth). A graph-only check would repeat the
  cave-lesson false-green. The graph is only the "what should be reachable" oracle.
- Scope creep guard: this is navigability (reachability + walkable surfaces).
  NOT enclosure/see-through, NOT aesthetic. Those stay manual for now (could be a
  later validator).
- EQ collision is per-triangle (lessons-learned) — the mesh IS the collision
  model, so a mesh-based walk is faithful to how the client actually moves.

### Build notes (this session)

- **Built the validator first** (the recommended path): it now objectively
  measures the `corridor-connection` fixes. The three known-bad seeds are `xfail`
  in the suite; when corridor-connection lands they'll flip to `xpass` and we
  drop the `xfail` markers (and promote a couple to `KNOWN_GOOD_DUNGEON`).
- **Validator confirms the corridor-connection diagnosis on live meshes.** The
  current layout realises the reported seeds slightly differently than the
  task's original measurements (the generator evolved), but the *failure classes*
  match exactly: oversized stair steps (8–17u vs a 3u step-up) and
  nominally-walkable-but-misaligned corridor openings. Example — dungeon seed 5
  has all-walkable corridors (0–10°) yet rooms are unreachable because the mesh
  openings don't meet (the same-axis L-bend bug). Flat seeds (1, 6, 26, 49) pass
  cleanly, so this is real breakage, not validator over-strictness.
- **New finding → logged as a ROADMAP Known issue:** outdoor (heightfield) and
  cave (organic) meshes are generated in a *different coordinate frame* than the
  room graph — the terrain starts at the origin going +X/+Y
  (`_heightfield_to_ter`: `x = i*res`) instead of centred on the rooms, so the
  terrain isn't under its rooms. That's why the validator can't map room
  footprints for those themes; the suite deliberately sweeps **dungeon only**.
  Reconciling the frames would extend the validator to outdoor/cave for free.
- **BLOCKER / needs the user's eyeball:** per the standing lesson (structural
  green ≠ actually navigable), one human 3D spot-check is still owed — load a
  flagged seed (e.g. 1955208177) in the viewer and confirm the rooms the
  validator calls unreachable really are. Everything programmatic is done and
  green; this is the last trust step before leaning on the validator to carry
  the section-B MUSTs.
