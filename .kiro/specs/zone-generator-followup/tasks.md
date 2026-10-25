# Implementation Plan: zone-generator-followup (the runway)

## Overview

This plan lands the **runway** for pluggable layout engines and a 3D layout
volume: the seams, contracts and the gate work that must exist before the real
engine/envelope features begin. It implements `requirements.md` and `design.md`
in this folder. "Req FN" means this spec's requirement; "Pn" / "Req X.Y" cite
the umbrella `zone-generator` spec.

**This milestone does not start until M1 lands** (it touches
`generators/layout.py`, the top of the pipeline). It is sequenced AFTER the
M1-M6 walkable-zones milestones.

The runway has one strict predecessor (task 1, the seam) and then three
independent tracks that fan out to parallel workers. The `Parallel-group` tag on
each task says which can run concurrently once their predecessor is in.

| Track | Tasks | Touches | Parallel-group |
|-------|-------|---------|----------------|
| Seam | 1 | `generators/layout.py` | - (must land first) |
| Schema | 2 | `ai/schema.py`, `generators/zone_spec.py` | A |
| Gate | 3 | `analyzer/traverse.py` | A |
| Harness | 4 | new `generators/engines/` + `tests/` | A (needs 1 + 2) |
| Register | 5 | `ROADMAP.md` + this spec | - (integration step) |

Working rules (inherited from the M1 plan): one worktree per track off the main
checkout with `./scripts/new-worktree.ps1`; commit one logical change at a time
via `.git/COMMIT_EDITMSG_TMP` then delete it; run `python -m pytest tests/ -q`
before each commit; a failing property is a real bug - fix at the root and pin
the counterexample, never weaken an assertion; tracker writes go to THIS
`tasks.md` only, with `ROADMAP.md` touched solely in the task-5 integration
step.

## Tasks

- [ ] 1. Extract the `LayoutEngine` seam (byte-identical)
  - [ ] 1.1 Capture the pre-refactor baseline
    - On the fork point, capture `sha256` of built TER for the project's pinned
      seeds x zone types x rooms x elevation on/off (the task-1.2 / 3.1 method).
      Record the hashes here. Throwaway script, not committed.
    - _Requirements: F1.2_
  - [ ] 1.2 Define `LayoutEngine` and move Job A behind it
    - Add the `LayoutEngine` protocol and a `TinyKeepEngine` wrapping today's
      `_scatter_rooms` -> `_separate_rooms` -> `_connect_rooms`, returning
      `(rooms, edges)`. `LayoutGenerator.generate()` calls the engine; Job B
      (pacing, semantics, elevation, crossings/conflicts, corridors, gating)
      is untouched.
    - _Requirements: F1.1_
  - [ ] 1.3 Prove byte-identity
    - Re-capture the task-1.1 hashes after the refactor; ALL must match. Record
      before/after in Deliverables. Suite green. No geometry moves.
    - _Requirements: F1.2_

- [ ] 2. Typed edges and the 3D `Envelope` in the schema  *(Parallel-group A; needs 1)*
  - [ ] 2.1 Grow `Edge` to `(i, j, kind, vhint)`
    - `kind in {floor, staircase, bridge, shaft}`, `vhint in {above, below,
      same, unset}`, defaulting to `floor` / `unset`. Loader tolerates and
      defaults absent fields. Existing specs round-trip unchanged.
    - _Requirements: F2.1, F2.3_
  - [ ] 2.2 Add the `Envelope` 3D-volume interface
    - `contains(x, y, z) -> bool`, optional `cost(x, y, z)`. A `FlatEnvelope`
      (thin volume) reproduces today; `envelope=None` is the default path.
    - _Requirements: F2.2_
  - [ ] 2.3 Property test: degenerate defaults == today
    - A zone built with default edge-kind / `vhint` / `envelope=None` is
      byte-identical to the pre-task-2 build for the pinned seeds.
    - **Validates: F2.1, F2.2, F2.3**

- [ ] 3. Traversability gate learns vertical connectors  *(Parallel-group A; needs only 1)*
  - [ ] 3.1 Model the staircase in `analyzer/traverse.py`
    - Walkable iff rise/run within the cap (start 1:2, tune to the agent),
      headroom present, a landing at top and bottom. Non-walkable cases
      (too steep, no headroom) are caught.
    - _Requirements: F4.1, F4.2_
  - [ ] 3.2 Model the bridge
    - A floor spanning a void; walkable iff continuous and within grade.
    - _Requirements: F4.1, F4.2_
  - [ ] 3.3 Property tests + pinned counterexamples
    - One property per connector kind; pin a known-bad staircase and a known-bad
      bridge as Regression_Examples. These land AHEAD of any generator that
      produces the geometry.
    - **Validates: F4.1, F4.2**

- [ ] 4. Side-by-side embedding harness  *(Parallel-group A; needs 1 + 2)*
  - [ ] 4.1 Selectable embedding strategies
    - `embed_abstract` and `embed_typed`, both consuming one mission graph +
      seed + `Envelope`, both emitting `(rooms, typed-edges)`.
    - _Requirements: F3.1_
  - [ ] 4.2 The evaluation record
    - Per (strategy, seed): gate result (reachability, connector walkability),
      connector counts by kind, a rendered view. Diffable output.
    - _Requirements: F3.2_
  - [ ] 4.3 Pin the seed set and the decision criterion
    - Known-good/known-bad seeds + ravine + church. Write the decision criterion
      (design.md) into the harness README so a run concludes.
    - _Requirements: F3.3, F3.4_

- [ ] 5. Register the milestone (integration step)
  - [ ] 5.1 ROADMAP line + board
    - Add the `zone-generator-followup` row to `ROADMAP.md`, sequenced after
      M6. Done as the serialized integration step, not during task work.
    - _Requirements: F1-F4 (tracker)_

## Explicitly NOT in this runway

The graph-rewrite engine, the continuous 3D connector router (real stair/bridge
geometry), and the concrete envelopes (ravine, stacked-volume church). Those are
the feature; they begin only after this runway lands and the side-by-side
harness has settled the typed-vs-abstract decision.
