# Requirements Document

> **STATUS: superseded** by the 11-step content roadmap in `ROADMAP.md`. This runway is no longer a milestone; its pieces land with roadmap steps 5, 6 and 7. Kept for reference — don't run these tasks.

## Introduction

`zone-generator-followup` is a **research + runway** spec for the next major
direction of the Zone_Generator: making the room-and-topology generation step
*pluggable*, and preparing the generator to lay zones out in a true 3D volume
(rooms that connect vertically) instead of only a flat plane.

It is deliberately scoped to the **prerequisites and the design**, not the
feature. It pairs with `design.md` (the target design, with the research that
backs it) and owns its own `tasks.md` (the runway that must land before the
real engine work begins). It cites the umbrella spec `zone-generator`
(`.kiro/specs/zone-generator/requirements.md` and `design.md`): "Req X.Y" below
means an umbrella requirement.

This work serves umbrella **pillar P-F, Iterative feedback (Req 18-20)**: an
explicit, editable topology that can be regenerated piece by piece is the
substrate iterative feedback needs, and a side-by-side evaluation harness is how
two design approaches are judged on evidence rather than argument.

**Ordering: this is a post-M1 milestone.** It touches the top half of the
generation pipeline (`generators/layout.py`), so it must not start while the
M1-M6 walkable-zones waves are in flight. The runway in `tasks.md` is written so
it can begin the moment M1 lands, and so its pieces fan out to parallel workers.

## Motivation (what we are reaching for)

1. **A pluggable generation stage.** Today `LayoutGenerator.generate()` hardcodes
   one algorithm (TinyKeep: scatter rooms, separate, Delaunay, MST + loops).
   We want the step that produces "a set of rooms and how they relate" to be a
   *selectable engine*, so a graph-rewrite engine (grow topology by rules, then
   lay it out) can sit beside the TinyKeep engine, both emitting the same
   room-and-edge contract the rest of the pipeline already consumes.

2. **A true 3D volume.** Rooms may connect vertically (a multi-level church, a
   ravine with rooms in opposite walls joined by a bridge). The spatial
   constraint the generator lays out within becomes a 3D `Envelope`, not a flat
   plane. The flat dungeon of today is the degenerate case (a thin volume).

3. **Evaluate design choices side by side.** The open design question (does the
   topology graph carry vertical relationships, or does the embedder decide all
   verticality?) is settled by building BOTH as selectable embedding strategies
   and comparing them on the same seed through the existing traversability gate
   and the 3D-eyeball pass, against a pre-committed decision criterion.

## Requirements

### Requirement F1 - Pluggable layout engine seam

**User story:** As a developer, I want the room-and-topology generation step
extracted behind one interface, so a new generation algorithm can be added
without touching the pacing, elevation, corridor and gating code downstream of
it.

#### Acceptance criteria

1. WHEN `LayoutGenerator.generate()` runs THEN the room-and-topology step
   (today `_scatter_rooms` -> `_separate_rooms` -> `_connect_rooms`) SHALL be
   reached through a `LayoutEngine` protocol returning the `(rooms, edges)`
   contract, with the current TinyKeep code as the first implementation.
2. WHEN the seam is extracted THEN every built TER SHALL be byte-identical to
   the pre-refactor build for the project's pinned seeds (the `routing.py`
   extraction method: capture sha256 before, compare after). *No geometry moves.*

### Requirement F2 - Typed edges and a 3D envelope in the schema

**User story:** As a developer, I want the data model to be able to express a
vertical connector and a 3D layout bound, added as defaulted fields so nothing
downstream breaks before the engines exist.

#### Acceptance criteria

1. An edge SHALL carry a `kind` (`floor | staircase | bridge | shaft`) and an
   optional vertical hint (`above | below | same | unset`); today's output is
   all `floor` / `unset` (the degenerate case), so existing zones are unchanged.
2. An `Envelope` SHALL describe a bounded 3D volume (a `contains(x, y, z)` test
   plus optional per-cell cost); the flat dungeon is a thin volume and remains
   the default.
3. WHEN the new fields are absent on load THEN the loader SHALL default them to
   the degenerate values (Req 11.1-style legacy tolerance).

### Requirement F3 - Side-by-side embedding evaluation harness

**User story:** As a designer, I want to run two embedding strategies on the
same mission graph and seed and compare them objectively, so the typed-vs-
abstract decision is made on evidence.

#### Acceptance criteria

1. The embedder SHALL be selectable (`embed_abstract` vs `embed_typed`), both
   consuming one mission graph + seed + `Envelope` and emitting the `(rooms,
   typed-edges)` contract.
2. For each variant on each pinned seed the harness SHALL record a diffable
   evaluation record: the traversability-gate result (reachability, connector
   walkability), connector counts by kind, and a rendered view.
3. The seed set SHALL include the project's known-good/known-bad seeds plus the
   two shape cases (ravine, church).
4. `design.md` SHALL state the decision criterion up front (what makes one
   strategy win) so the comparison can conclude rather than run forever.

### Requirement F4 - Traversability gate learns vertical connectors first

**User story:** As a developer, I want the traversability validator to
understand staircases and bridges BEFORE any vertical zone is generated,
because structural tests passing is necessary but not sufficient in this
project (every corridor bug so far passed the suite and was caught only in 3D).

#### Acceptance criteria

1. `analyzer/traverse.py` SHALL model a staircase (rise/run/headroom) and a
   bridge (a floor spanning a void) as walkable connectors, with property tests,
   landed ahead of the engine/envelope work that produces that geometry.
2. A vertical connector that is not actually walkable (too steep, no headroom,
   a gap) SHALL be caught by the gate, pinned as a Regression_Example.

## Explicitly out of scope (the work, not the runway)

Named so the runway stays bounded: the graph-rewrite engine itself; the
continuous-coordinate 3D connector router (stairs/bridges in real geometry); and
the concrete `Envelope` implementations (ravine, stacked-volume church). Those
are the feature, and they begin only after this runway lands.

## Sources

The design is grounded in prior art, cited in `design.md`: Dormans' mission /
space grammar split (dimension-free mission layer; his 2D space grammar is
discarded for a 3D game); Boris the Brave's deconstruction of Unexplored
(graph rewriting operates on an abstract, coordinate-free graph); and vazgriz's
3D extension of the TinyKeep algorithm (Delaunay tetrahedralization + 3D A*
staircases), the closest shipped prior art because it is this project's own
algorithm already solved in 3D.
