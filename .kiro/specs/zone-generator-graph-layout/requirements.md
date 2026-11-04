# Requirements Document

> **STATUS: roadmap step 6, ready.** Written 2026-11-03 at master `67e5b69`;
> the user settled the open questions the same day (`archive.md`
> "Decisions"). Task index: `tasks.md` (card format, 21 tasks).

## Introduction

Roadmap step 6: **graph-replacement dungeon generation.** Today every room
zone gets its room graph the same way (TinyKeep): rooms are scattered in an
ellipse, pushed apart, joined by a Delaunay triangulation cut down to a
spanning tree, and a few loop edges are added back. The graph is a side
effect of where the rooms happened to land, and nothing can ask for a shape.

This step adds a second way to make the room graph, by **graph rewriting**
as shaggydev's "Graph rewriting" article (2022-11-20) lays it out: start from
a small graph with placeholder nodes, apply rules that each find a pattern
and replace it with a bigger structure, following a recipe of stages, until
no placeholder is left. Then place the rooms (a spring layout: connected
rooms pull together, all rooms push apart) and create the connections as
corridors. Everything after the graph (pacing, themes, elevation, corridors,
locks, the walkability gate, maps, textures) runs as today.

The rules are the extension point. They live in **rule-set files** a person
(and later a prompt) can write, are checked strictly on load, and are drawn
as before → after diagrams. Rules decide each room's size class and how
rooms relate, including vertically, so that later steps (stacked levels,
room shapes, districts' looks) read rules written now without rewriting
them.

What this is not: the Dormans mission grammar of locks and keys, which ROADMAP
"Deliberately NOT doing" rules out ("EQ gates by depth/danger, not Zelda-style
lock chains"). The rules shape the topology and the rooms' sizes; locks stay
with today's solvable gating.

This step pulls in the last piece of the retired `zone-generator-followup`
runway: the pluggable `LayoutEngine` seam (its Requirement F1). The vertical
relations in the rule format are the followup's typed-edge hint (F2); acting
on them with stacked rooms and stairs, and the gate learning stairs (F4), is
step 7.

This spec sits under the umbrella `zone-generator`
(`.kiro/specs/zone-generator/`). "Req X.Y" below means a requirement of THIS
spec unless it says "umbrella".

**Out of step 6:** prompt words that choose a topology (a fast follow, see
`archive.md` "Follow-ups"), stacked rooms and vertical connectors (step 7),
room shapes other than rectangles (step 8; the format carries `shape` now),
what's inside rooms (step 9), the look of districts (their materials and
lights, umbrella Req 23.5; the rules mark district structure only), and the
in-client check (M6).

## Glossary

- **Layout_Engine**: the part of the layout that produces the rooms (their
  footprints, before pacing) and the room graph's edges. Everything after it
  is shared by all engines.
- **Classic_Engine**: today's TinyKeep scheme, behind the Layout_Engine seam.
- **Graph_Engine**: the new engine: a Rule_Set's recipe grows a
  Topology_Graph, then a Placement places its rooms.
- **Topology_Graph**: an abstract room graph with no coordinates. A node has a
  kind (the placeholder `Area`, or a room kind such as `entrance`, `chamber`,
  `lair`) and, for rooms, a Size_Class, plus optional `shape` and
  `district`. An edge has an optional Vertical_Relation and optional tags.
- **Rewrite_Rule**: a match (a small subgraph of node kinds and edges), a
  replacement subgraph, and where the match's outside connections reattach,
  with an optional `when` condition on the build's context.
- **Recipe**: the ordered stages a Rule_Set grows a graph by; each stage names
  the rules it may apply (with weights) and its share of the rooms.
- **Rule_Set**: one file holding a start graph, Rewrite_Rules, a Recipe and a
  named Placement. Step 6 ships two base sets: `classic_eq` and `warren`.
- **Theme_Layer**: a file that adds rules and recipe stages to a base set for
  one dungeon theme (e.g. a temple's nave and chapels).
- **Size_Class**: `tiny`, `small`, `medium`, `large` or `huge`; turned into
  units after the rules, from the zone type's measured room size and then the
  race's scale.
- **Vertical_Relation**: on an edge, `above`, `below`, `level` or `any`
  (the default): where the second room sits relative to the first.
- **Placement**: the function that places a finished Topology_Graph's rooms in
  the plane; named by the Rule_Set (`spring` in step 6).
- **Edge_Fidelity**: the share of the Topology_Graph's edges that survive as
  corridors after the shared layout steps (crossing splits, conflict drops).

## Requirements

### Requirement 1: Measure the stock dungeon topology

**User Story:** As the project owner, I want the stock dungeons' room graphs
measured, so that the rule sets grow graphs shaped like EQ's.

1. A survey SHALL walk each listed stock dungeon's floor (the WLD walk the
   traversal agent uses), split it into chambers and passages by floor width,
   and report per zone: chamber count, chamber sizes, each chamber's degree,
   the cycle rank (E − N + 1), the dead-end share, and the deep-end distance
   (the longest shortest path from the entry chamber over the chamber count).
2. The survey SHALL report the warren-like zones (Blackburrow, Runnyeye) apart
   from the rest, so that `classic_eq` and `warren` each get their own bands
   (Req 5).
3. IF the width split gives a graph that a person reading the zone's map can
   see is wrong, THEN the findings SHALL say so and leave that zone out of the
   bands.

### Requirement 2: Layout_Engine seam

**User Story:** As a developer, I want the room-and-graph step behind one
interface, so that a new engine can be added without touching what comes
after it.

1. `LayoutGenerator` SHALL get its rooms and edges from a Layout_Engine, with
   the TinyKeep code as the Classic_Engine.
2. With the Classic_Engine every build SHALL be byte-for-byte what it is today
   for dungeon, city, wilderness and outdoor-dungeon zones (Zone_Spec JSON and
   `.eqg` contents, footer aside, on pinned seeds captured before the change).
3. The seam SHALL take the Envelope, so that an engine can lay out an outdoor
   dungeon.

### Requirement 3: Rule-set files and their checks

**User Story:** As a rule author (a person now, a prompt later), I want rule
sets in plain files with exact error messages, so that writing and fixing a
rule never needs a code change.

1. A Rule_Set and a Theme_Layer SHALL each be one TOML file under
   `rules/topology/`, declaring their rules, start graph, Recipe and
   Placement as data (design "Rule-set files").
2. Loading SHALL check every file completely and report every problem found,
   each naming the file, the rule or stage, the field and what was expected:
   unknown kinds, Size_Classes, Vertical_Relations or condition keys; edges
   naming nodes that don't exist; outside connections left with nowhere to
   reattach; a room node without a Size_Class; a stage naming an unknown rule;
   shares that don't add up; a layer naming a base set it doesn't fit.
3. A file that fails a check SHALL NOT be used; the build SHALL fail with the
   check's report, not fall back silently.
4. A dry-run command SHALL grow a given number of graphs from a Rule_Set (with
   any layers) over seeds and room counts and report stages that can't
   complete, rules that never fire, and the shape measures reached.
5. A draw command SHALL render each rule of a set as a before → after diagram
   (node kinds, Size_Classes, edges, Vertical_Relations, reattachment) into
   one page per set.
6. An authoring guide SHALL explain the format with the shipped sets as worked
   examples, and say how to check, dry-run and draw a set.

### Requirement 4: Growing the graph

**User Story:** As a developer, I want the graph grown by rules that can't
loop forever or break the graph, so that growing is safe and reproducible.

1. The grammar SHALL start from the Rule_Set's start graph and run its Recipe:
   each stage applies its rules (picked by weight among their matches, with
   `when` conditions tested against the build's context) for its share of the
   requested rooms; a final stage turns every remaining `Area` into a room, so
   that the graph holds exactly the requested number of rooms (1–30).
2. After every applied rule the graph SHALL be connected, no room SHALL have
   more than 4 connections (a room opens at most one wall per side), and each
   loop SHALL close over a bounded number of rooms; an application that would
   break one of these, or leave the requested room count unreachable, SHALL be
   rejected and the graph kept as it was.
3. The driver SHALL stop within a hard step cap and raise an error naming the
   Rule_Set, the stage and the cap if it is reached, never loop.
4. The same seed, Rule_Set, layers and inputs SHALL give the same
   Topology_Graph.
5. A Theme_Layer SHALL add its rules and stages to its base set when that
   theme is built, without the base set's file changing.

### Requirement 5: Two rule sets, shaped like their stock zones

**User Story:** As a user, I want grown dungeons to have the shape of classic
ones, and a warren to feel like a warren.

1. Over many seeds and room counts, `classic_eq`'s graphs SHALL fall inside the
   survey's bands for the classic dungeons, and `warren`'s inside the
   warren-like zones' bands (dead-end share, cycle rank per room, deep-end
   distance, Size_Class mix).
2. `warren` SHALL differ from `classic_eq` in the direction its stock zones do
   (task 1 states the direction; expected: smaller rooms, more dead ends,
   more short loops).
3. At least one Theme_Layer (`temple`: a nave with side chapels) SHALL ship, to
   prove layering.

### Requirement 6: Placement and room sizes

**User Story:** As a user, I want the rooms placed so that the dungeon has the
graph and the room sizes the rules chose, with corridors as good as today's.

1. Each room's footprint and height SHALL come from its Size_Class (design
   "Size classes"), then the race's scale as today; pacing roles SHALL NOT
   resize grown rooms (the rules own size).
2. The Placement SHALL place rooms by a spring layout over the Topology_Graph,
   then resolve every footprint overlap with the same separation and corridor
   clearance the Classic_Engine's rooms get. No two rooms SHALL overlap in plan
   (no stacking in step 6, intended or not).
3. The Topology_Graph's `entrance` room SHALL be the layout's entrance room
   (pacing still derives every role from the graph, umbrella Req 32.2).
4. The room graph after the shared layout steps SHALL be connected for every
   seed, and its mean Edge_Fidelity SHALL be at least the design's bar.
5. An edge's `above` or `below` SHALL set the direction of the elevation
   change on its corridor (within the existing grade cap); `level` SHALL keep
   both floors equal; `any` SHALL behave as today.
6. WITH an Envelope, the grown rooms SHALL fit it as the Classic_Engine's do,
   dropping rooms with the `rooms_reduced` warning when they don't.

### Requirement 7: Choosing the engine and the rule set

1. A Layout toggle (`classic` | `graph`) SHALL pick the engine from the
   Controls panel, the CLI and the server, for `dungeon` and
   `outdoor_dungeon` zones; `graph` is the default (task 21; a plan saved
   without the field rebuilds `classic`).
2. With `graph`, the rule set SHALL come from the dungeon theme (each theme
   names its base set and layers; no theme gives `classic_eq`), unless the
   request names a base set.
3. A plan or request without the toggle SHALL build the same Zone_Spec and
   `.eqg` contents as today (the sidecar may gain the `layout` block).
4. Each theme SHALL map the rules' room kinds onto its own room types (e.g. a
   fortress's `deep` is its throne room); rules set kinds, themes set types.
5. The sidecar SHALL record the engine, the base set and layers, the rules
   applied in order, each room's kind, Size_Class and district, the
   Topology_Graph's shape measures and the Edge_Fidelity.

### Requirement 8: Everything after the graph holds

1. Themes, elevation, corridors, locks and maps SHALL run on grown layouts;
   umbrella Req 21 (one entrance, one climax, solvable locks) SHALL hold.
2. Grown builds SHALL pass the walkability gate as classic builds do, retried
   on a fresh seed on failure like any gate failure.
3. The same inputs SHALL give byte-identical `.eqg` contents (footer aside).
4. A grown build SHALL take no longer than a classic build of the same room
   count plus 10 s on the reference machine.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge
   it, a step in `docs/ACCEPTANCE.md` "Step 6 — Graph layouts".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass comparing classic and graph dungeons on the
   same seeds, and says whether `graph` becomes the default (recorded at the
   close).
