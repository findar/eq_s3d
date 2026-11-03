# Requirements Document

> **STATUS: roadmap step 6, DRAFT: open questions not answered yet.** Written
> 2026-11-03 at master `67e5b69`. The design's open questions need the user's
> answers before any task starts (`design.md` "Open questions"; answers go in
> `archive.md` "Decisions"). Task index: `tasks.md` (card format, 14 tasks).

## Introduction

Roadmap step 6: **graph-replacement dungeon generation.** Today every room
zone gets its room graph the same way (TinyKeep): rooms are scattered in an
ellipse, pushed apart, joined by a Delaunay triangulation cut down to a
spanning tree, and a few loop edges are added back. The graph is a side
effect of where the rooms happened to land. Its shape can't be asked for:
not a long winding spine, a wing of side rooms, a loop back to the start, or
a deep end.

This step adds a second way to make the room graph: **grow** it. Start from a
small graph and rewrite it with rules (extend the spine, add a branch, close
a loop, add a wing) until it has the requested number of rooms, then place the
rooms in the plane to fit that graph. Everything after the graph (pacing,
themes, elevation, corridors, locks, the walkability gate, maps, textures)
runs unchanged.

What this is not: the Dormans mission grammar of locks and keys, which ROADMAP
"Deliberately NOT doing" rules out ("EQ gates by depth/danger, not Zelda-style
lock chains"). The rules here shape the **topology** (how far the deep end is,
how many dead ends and loops), measured from stock EQ dungeons. Locks stay
with today's solvable gating.

This step pulls in the last piece of the retired `zone-generator-followup`
runway: the pluggable `LayoutEngine` seam (its Requirement F1). Typed edges
and vertical hints (its F2) and the gate learning staircases (its F4) stay with
step 7, and its side-by-side embedding harness (F3) is replaced here by a
human comparison of the two engines on the same seeds.

This spec sits under the umbrella `zone-generator`
(`.kiro/specs/zone-generator/`). "Req X.Y" below means a requirement of THIS
spec unless it says "umbrella". The umbrella's topology control (umbrella
Req 22) is not built yet; Open question 2 asks whether this step builds it.

**Out of step 6:** districts (umbrella Req 23), multi-level layouts and
vertical connectors (step 7), room wall styles (step 8), what's inside rooms
(step 9), and the in-client check (M6).

## Glossary

- **Layout_Engine**: the part of the layout that produces the rooms (their
  footprints, before pacing) and the room graph's edges. Everything after it is
  shared by all engines.
- **Classic_Engine**: today's TinyKeep scheme, behind the Layout_Engine seam.
- **Grown_Engine**: the new engine: Topology_Grammar, then Embedding.
- **Topology_Graph**: an abstract room graph with no coordinates: nodes are
  rooms, edges are connections, each node tagged with how it was made (spine,
  branch, loop, wing).
- **Topology_Grammar**: the rewrite rules and the driver that applies them to
  a Topology_Graph, checking the invariants at every step.
- **Topology_Profile**: a set of rule weights (`linear`, `branching`,
  `looped`) that gives a family of graph shapes.
- **Embedding**: placing a Topology_Graph's rooms in the plane so that the
  existing corridor router can join every edge.
- **Edge_Fidelity**: the share of the Topology_Graph's edges that survive as
  corridors after the shared layout steps (crossing splits, conflict drops).

## Requirements

### Requirement 1: Measure the classic dungeon topology

**User Story:** As the project owner, I want the stock dungeons' room graphs
measured, so that the grown graphs are shaped like EQ's and not like a
roguelike's.

1. A survey SHALL walk each listed classic dungeon's floor (the WLD walk the
   traversal agent uses) and split it into chambers and passages by floor
   width, and report per zone: chamber count, the degree of each chamber, the
   cycle rank (E − N + 1), the share of dead ends (degree 1), and the longest
   shortest path from the entry chamber as a share of the chamber count.
2. The survey's numbers SHALL be written into the design's research findings
   and set the Topology_Profiles' weights and the bands of Req 4.
3. IF the width split gives graphs a person reading the zone's map can see are
   wrong, THEN the survey SHALL say so in the findings and the bands SHALL be
   set from the zones it does get right, naming them.

### Requirement 2: Layout_Engine seam

**User Story:** As a developer, I want the room-and-graph step behind one
interface, so that a new engine can be added without touching what comes
after it.

1. `LayoutGenerator` SHALL get its rooms and edges from a Layout_Engine, with
   the TinyKeep code as the Classic_Engine.
2. With the Classic_Engine every build SHALL be byte-for-byte what it is today
   for dungeon, city, wilderness and outdoor-dungeon zones (Zone_Spec JSON and
   `.eqg` contents, footer aside, on pinned seeds captured before the change).
3. The seam SHALL take the Envelope, so an engine can lay out an outdoor
   dungeon.

### Requirement 3: Topology_Grammar

**User Story:** As a developer, I want the graph grown by rules that can't
loop forever or break the graph, so that growing is safe and reproducible.

1. The grammar SHALL start from a fixed start graph and apply weighted rules
   until the graph has exactly the requested number of rooms (1–30).
2. After every applied rule the graph SHALL be connected, no room SHALL have
   more than 4 connections (a room opens at most one wall per side), and each
   loop SHALL close over a bounded number of rooms; a rule application that
   would break one of these SHALL be rejected and the graph kept as it was.
3. The driver SHALL stop within a hard step cap and raise an error naming the
   cap if it is reached, never loop.
4. The same seed and inputs SHALL give the same Topology_Graph.

### Requirement 4: Graph shape

**User Story:** As a user, I want grown dungeons to have the shape of classic
ones: a deep end worth reaching, side rooms, the odd loop.

1. Over many seeds per profile and room count, the grown graphs' dead-end
   share, cycle rank per room, and deep-end distance SHALL fall inside the
   bands set from the survey (Req 1.2).
2. The profiles SHALL differ as umbrella Req 22 asks: `linear` graphs have
   maximum degree at most 3 with at least n − 3 rooms of degree at most 2, and
   for 14 rooms the cycle ranks order `linear` ≤ `branching` < `looped`.

### Requirement 5: Embedding

**User Story:** As a user, I want the rooms placed so the dungeon has the
graph that was grown, with the corridors and walls as good as today's.

1. The Embedding SHALL place every room with no footprint overlap and the
   same corridor clearance the Classic_Engine's rooms get.
2. The room graph after the shared layout steps SHALL be connected for every
   seed, and its Edge_Fidelity SHALL be at least the design's bar on average
   over the sweep seeds (design "Embedding").
3. WITH an Envelope, the grown rooms SHALL fit it as the Classic_Engine's do,
   dropping rooms with the `rooms_reduced` warning when they don't.

### Requirement 6: Choosing the engine

1. A layout option (Open question 1 names it) SHALL pick the engine and
   profile from the Controls panel, the CLI, the server and the prompt
   ("winding", "maze", "sprawling" and the like), for the zone types Open
   question 3 settles.
2. A plan or request without the option SHALL build the same Zone_Spec and
   `.eqg` contents as today (the sidecar may gain the `layout` block).
3. The sidecar SHALL record the engine, the profile, the rules applied (counts
   by rule), the Topology_Graph's measured shape, and the Edge_Fidelity.

### Requirement 7: Everything after the graph unchanged

1. Pacing roles, themes, elevation, corridors, locks and maps SHALL run
   unchanged on grown layouts; umbrella Req 21 (one entrance, one climax,
   solvable locks) SHALL hold.
2. Grown builds SHALL pass the walkability gate as classic builds do, retried
   on a fresh seed on failure like any gate failure.
3. The same inputs SHALL give byte-identical `.eqg` contents (footer aside).
4. A grown build SHALL take no longer than a classic build of the same room
   count plus 10 s on the reference machine.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge
   it, a step in `docs/ACCEPTANCE.md` "Step 6 — Grown layouts".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass comparing classic and grown dungeons on the
   same seeds, and says whether grown becomes the default (recorded at the
   close).
