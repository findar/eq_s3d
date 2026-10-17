# TASK: traversability-validator

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Validation tooling (serves the "navigable" north-star; reduces manual UAT)
Last touched: created after commit d5daf00

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

- [ ] Loads a generated zone (`.eqg`/TER, via the existing `core` readers) and
      an agent model (EQ scale: height ~6u, walkable slope cap, max step-up),
      and produces a pass/fail + per-room reachability report from the safe
      point / entrance.
- [ ] Correctly FAILS the known-bad seeds (1955208177 at minimum: the 53° ramp
      and the ~15u-step stairs must be reported as non-traversable) and names
      the offending corridor/room and the reason.
- [ ] Correctly PASSES known-good flat/gently-elevated zones (no false alarms).
- [ ] Runnable as a CLI (e.g. `python -m analyzer.traverse output/<zone>.eqg`
      or against a seed) with a readable report.
- [ ] Backed by a pytest that sweeps several seeds per theme and asserts every
      room is reachable (so regressions are caught in the suite, not by eye).
- [ ] Documented: `docs/ACCEPTANCE.md` updated to note which section-B MUSTs the
      validator now covers automatically vs. what still needs a human.

## Subtasks

- [ ] Decide the agent model + thresholds (walkable slope cap, max step-up
      height, agent radius/height) grounded in EQ scale and the terrain
      backend's existing `max_walkable_grad`. Record the numbers + rationale.
- [ ] Surface extraction: from the TER triangles, classify "standable" faces
      (normal.z above a threshold) and build adjacency between standable patches
      that are horizontally overlapping and within the step-up height.
- [ ] Reachability flood-fill from the safe point; map each room's floor
      footprint to the reachable set; report unreachable rooms + the likely
      cause (no adjacent standable face within step height = cliff/gap; slope
      too steep = unwalkable ramp; etc.).
- [ ] CLI entry point with a clear report (reachable N/total rooms, per-failure
      reason, offending corridor id where derivable).
- [ ] Seed-sweep pytest (e.g. `tests/test_traversability.py`) over several
      seeds/themes; assert full reachability for known-good, and keep the
      known-bad seeds as xfail/annotated until `corridor-connection` lands.
- [ ] Validate the validator: confirm it flags 1955208177 and passes a known-good
      seed; spot-check one result against the actual 3D viewer so we trust it.
- [ ] Wire into `docs/ACCEPTANCE.md` (which section-B items are now automated)
      and note in ROADMAP.

## Deliverables

- Code: `analyzer/traverse.py` (or similar) + CLI
- Tests: `tests/test_traversability.py`
- Docs: `docs/ACCEPTANCE.md` (automated-vs-manual split), ROADMAP; this file
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
