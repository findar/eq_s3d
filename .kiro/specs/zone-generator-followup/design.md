# Design Document: zone-generator-followup

## Overview

This design turns the room-and-topology generation step into a pluggable
engine, prepares the generator for a true 3D layout volume, and sets up a
side-by-side evaluation harness for the one genuinely open design question
(does the topology graph carry vertical relationships, or does the embedder
decide all verticality?).

It is a **design + runway** spec. The runway (its `tasks.md`) lands the seams
and contracts; the engines, the 3D connector router and the concrete envelopes
are later work that builds on this runway.

## Research: what existing work does

Two camps in the literature, and they split cleanly along the axis that matters
to us: **who owns verticality.**

### Topology camp - graph grammars (Dormans / Unexplored)

Joris Dormans' mission/space split is the foundation of the "graph replacement"
idea. It has two grammars at two layers:

- **Mission grammar** - rewrites an abstract graph of *tasks and relationships*
  (lock -> key, boss-at-end, branch, loop). **No geometry, no dimension.** It is
  true of a 2D game, a 3D game, or a board game alike. Boris the Brave's
  deconstruction of Unexplored confirms the rewrite rules operate on a
  coordinate-free graph; geometry is assigned later.
- **Space grammar** - embeds the mission into a concrete layout. Dormans' space
  grammar is **2D (tile/grid)** and Unexplored ships 2D.

**Consequence for us:** reuse the mission layer (dimension-free, still
valuable); discard the space layer (it is the 2D part, and we are a 3D game).
The embedding is exactly the part we replace with a 3D `Envelope` and our own
continuous geometry.

### Spatial camp - TinyKeep lineage, extended to 3D (vazgriz)

The decisive prior art is **vazgriz**, who took TinyKeep's exact algorithm - the
one `generators/layout.py` implements today - and extended it to 3D for
multi-floor dungeons. An independent Unreal plugin (`draquel/ProceduralDungeonPlugin`)
converged on the identical recipe, a strong signal. vazgriz's path:

1. Rooms placed in a 3D grid (note: only a few cells tall).
2. **Delaunay tetrahedralization** (4-vertex cells; at least one vertex on
   another floor - this is what creates vertical adjacency) instead of 2D
   triangulation.
3. MST + loop edges - unchanged from 2D.
4. **3D A* with staircases** - where ALL the difficulty concentrated.

vazgriz's honest findings, which drive our risk assessment:

- Making rooms 3D was **"trivial."**
- 3D Delaunay was **annoying but bounded** (he ported Bowyer-Watson to
  circumspheres himself; no MIT source existed).
- **3D A* "is where it gets complicated."** The whole difficulty collapsed onto
  the **staircase**: rise AND run (he used 1:2), headroom (4 cells occupied),
  a guaranteed hallway at top and bottom, and a pathfinder that must route
  around staircases it just created (forcing each node to remember its path).

### The bar-raiser verdict

- **Go 3D volume for the `Envelope`.** A 2D footprint mask cannot express a room
  on a ravine wall at height, nor a church whose floors are intentionally
  stacked; it would force a rewrite the moment either is attempted. The 3D
  volume subsumes the flat case (flat = thin volume), so there is no migration.
- **The volume is cheap; the vertical connector is the whole project.** Per
  vazgriz, the hard, risky work is the staircase/bridge that actually passes a
  walkability check. This maps directly onto this project's scar tissue:
  corridor bugs that passed every structural test and were caught only in the
  3D viewer. Therefore: **gate before generator** (Requirement F4).
- **Borrow vazgriz's topology, not his grid.** He discretizes to a grid and uses
  grid A*; our north star is non-grid, continuous-coordinate, natural geometry.
  We take the tetrahedralization, the edge-kinds and the staircase CONSTRAINTS
  (rise/run/headroom) but adapt the connector to our continuous router. That is
  more work than his version, and it is the price of the aesthetic.

## Architecture

Three layers, two of them dimension-free, one 3D-specific and ours:

```
Mission grammar      (dimension-free - reuse Dormans; lock/key/boss/loop; no coords)
        |
        v  emits an abstract graph (rooms + relationships, no geometry)
Embedding / layout   (3D-SPECIFIC, OUR WORK - replaces Dormans' 2D grid grammar;
        |             consumes the 3D Envelope; continuous geometry)
        v  emits (rooms at x,y,z + typed edges)
Geometry + gate      (3D, already ours - ZoneBuilder, routing, traversability;
                      extended for staircases/bridges)
```

### The engine seam (Requirement F1)

`LayoutGenerator.generate()` today glues two jobs:

- **Job A** - produce rooms + topology: `_scatter_rooms` -> `_separate_rooms`
  -> `_connect_rooms`. *This is the swappable engine.*
- **Job B** - everything after: pacing, semantics, elevation relaxation,
  crossing/conflict resolution, corridor routing, gating, the traversability
  gate. *Engine-agnostic; runs unchanged.*

Extract Job A behind a protocol:

```python
class LayoutEngine(Protocol):
    def generate(self, room_count: int, rng: Random, scale: RoomScale,
                 envelope: "Envelope | None" = None) -> tuple[list[RoomSpec],
                                                               list[Edge]]:
        ...
```

TinyKeep is the first implementation, proven byte-identical by the same
sha256-capture method the `generators/routing.py` extraction already used
(capture pinned-seed TER hashes before, compare after; no geometry moves). A
graph-rewrite engine is a later implementation behind the same protocol.

### Typed edges and the 3D envelope (Requirement F2)

- `Edge` grows from `(i, j)` to `(i, j, kind, vhint)`:
  - `kind in {floor, staircase, bridge, shaft}`
  - `vhint in {above, below, same, unset}`
  - today's output is `kind=floor, vhint=unset` (the degenerate case).
- `Envelope` is a bounded 3D volume:
  - `contains(x, y, z) -> bool`, optional `cost(x, y, z) -> float`.
  - the flat dungeon is a thin volume; `envelope=None` reproduces today exactly.
- Both are additive, defaulted fields in `ai/schema.py` / `generators/zone_spec.py`,
  tolerated-and-defaulted on load, so nothing downstream breaks before the
  engines consume them.

### The side-by-side harness (Requirement F3)

One mission graph, one seed, two embedding strategies, two built zones, the same
gate against both, both rendered for comparison. The embedder is a selectable
strategy one layer below the engine:

- `embed_abstract` - the graph stays abstract ("A connects to B"); the embedder
  owns ALL verticality (Dormans' pure separation).
- `embed_typed` - edges carry optional `vhint`; the embedder must honor
  `above/below` (the 3D-native stance, for intentional vertical structure like
  the church bell tower above the nave).

The harness emits a **diffable evaluation record** per (strategy, seed):
gate result (reachability, connector walkability), connector counts by kind, a
rendered view. Seed set = pinned known-good/known-bad seeds + the ravine and
church shape cases.

**Decision criterion (committed up front, so the comparison concludes):** adopt
typed edges iff they produce intentional vertical structure that abstract
embedding fails to produce (demonstrated on the church case) AND both strategies
pass the traversability gate at equal rates on the pinned seed set. If typed
edges do not earn their complexity by that bar, keep the graph abstract.

### Gate learns connectors first (Requirement F4)

Before any vertical zone is generated, `analyzer/traverse.py` learns:

- **staircase**: walkable iff rise/run within the cap (start from vazgriz's 1:2),
  headroom present, a landing (hallway) at top and bottom.
- **bridge**: a floor spanning a void, walkable iff continuous and within grade.

Each ships with a property test; a non-walkable connector (too steep, no
headroom, a gap) is caught and pinned as a Regression_Example. This is the one
medium-risk piece and it leads, not follows.

## Why this maps to parallel work

Once F1 (the seam) lands, F2 (schema), F3 (harness) and F4 (gate) touch
different files - `ai/schema.py` + `generators/zone_spec.py`, a new harness
module, and `analyzer/traverse.py` - so they run as three concurrent workers in
separate worktrees. The seam extraction is the only strict predecessor. This is
the throughput shape the whole discussion was aiming at: requirements written
ahead, dependencies explicit, independent pieces fanned out.

## Open decisions left for the runway

- The exact `RoomScale` / rng threading into `LayoutEngine.generate` (match
  today's signature precisely during extraction).
- Whether `Envelope` exposes a discrete cell grid or a pure continuous predicate
  (continuous preferred, per the north star; revisit if the connector router
  needs cells).
- The staircase rise/run cap for THIS project's agent model (vazgriz's 1:2 is a
  starting point, not a given; tune against `analyzer/traverse.py`'s agent).
