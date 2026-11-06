# Requirements Document

> **STATUS: roadmap step 8, draft.** Written 2026-11-06 at master `d09449c`.
> The design's open questions wait on the user. Task index: `tasks.md` (card
> format, 16 tasks).

## Introduction

Roadmap step 8: **interesting room walls, rough cave vs man-made cave vs
dungeon.** Every room built today is a box: four flat walls, a flat floor and a
flat ceiling. The user's step 6 first look found dungeons hard to tell apart
for this reason, and asked for rooms more interesting than rectangles, naming a
Voronoi diagram as a way to get there.

Measuring 25 stock zones for this spec changed the shape of the problem (design
finding 1): **stock cave walls are vertical.** In Blackburrow 99% of the wall
area is within 3° of plumb. A stock cave is an irregular outline stood straight
up, with a floor and ceiling that move, and not a blobby volume. So this step
needs no voxels or signed distance fields, which is what the removed cave
pipeline used and what failed: rooms stay vertical prisms over an outline.

Step 6 and 7 left these hooks:

- **A `shape` attribute in the rule format,** accepting only `rect` today
  (`generators/topology/graph.py` `SHAPES`).
- **Room kinds** (`hall`, `lair`, `hub`, `deep`) that don't yet show in 3D.
- **Stock scale:** room and corridor sizes come from the race's body height H,
  so a wall's detail can too.

This spec sits under the umbrella `zone-generator`
(`.kiro/specs/zone-generator/`). "Req X.Y" below means a requirement of THIS
spec unless it says "umbrella". It replaces the umbrella's sketch of an M5
natural geometry style and answers that sketch's open question (design
"Decisions").

**Out of step 8:** what's inside rooms: pillars, stalactites, POIs (step 9) and
decoration (step 11); rough stairs and bridges (they stay as built, design
Open question 5); cities and wilderness; the Classic engine (Open question 3);
and the in-client check (M6).

## Glossary

- **Box**: a room's `RoomSpec` rectangle and height. It stays the room's
  allotment: placement, stacking, corridors and the Envelope all still use it.
- **Outline**: the room's actual walls in plan, a closed shape inside the Box.
- **Cell**: one convex piece of floor plan. An Outline is the edge of a
  connected set of Cells.
- **Cell_Complex**: the Cells a room's Box is divided into, before some are
  chosen: a Voronoi diagram for caves, a grid for built rooms.
- **Core**: the Cells that always stay in, around the Box's centre, so the
  spawn, labels and the gate's room tests still land on floor.
- **Throat**: the straight strip of floor inside a door, as wide as its
  corridor, joining the door to the Core.
- **Wall_Style**: how a zone's rooms are drawn: `built` (dungeon masonry),
  `hewn` (man-made cave), `rough` (natural cave).
- **Relief**: how far a room's floor and ceiling move away from flat.
- **Axis_Share**: the share of wall area whose direction is within 5° of the
  zone's main grid. It's the survey's measure of how man-made walls are.
- **Fill**: a room's floor area over the area of its bounding box.

## Requirements

### Requirement 1: Measure the stock walls

**User Story:** As the project owner, I want stock room walls measured, so that
the three styles are set from real zones and not my impressions of them.

1. A survey SHALL report per zone: Axis_Share, the plumb share of the walls, the
   median wall triangle edge, the length of straight wall runs, the corners per
   room, Fill, the floor's and ceiling's Relief and their flat share.
2. The zones SHALL be sorted into the three styles by looking at plan and side
   plots, with zones that don't separate named and left out.
3. The numbers SHALL set each style's bands (Req 12) and parameters (Req 5).

### Requirement 2: Outlines

**User Story:** As a player, I want rooms of many shapes, with every door still
leading into the room.

1. A room MAY carry an Outline, built from a chosen connected set of Cells.
2. An Outline SHALL lie inside its Box, contain the Box's centre (the Core), and
   reach every door, the Outdoor Tunnel and every Bridge slot through a Throat.
3. A room's Fill SHALL fall inside its style's band, unless its doors need more
   floor; no Outline's Fill SHALL fall under the design's floor.
4. The Outline SHALL be a pure function of the room, its doors, the style and
   the seed (Req 12.5), and the rng draws for it SHALL not change the layout.
5. Rooms with no Outline SHALL build exactly as today, byte for byte.

### Requirement 3: The gate knows Outlines first

**User Story:** As a developer, I want the gate to catch a broken shape before
any generator makes one.

1. The gate SHALL check on any room with an Outline: every door's Throat is
   walkable from the Core, no wall crosses a Throat, and the room's surface is
   closed (no gap through which the void shows, apart from doors and slots).
2. Each failure SHALL be named in the gate's diagnosis and pinned as a
   regression example.
3. These checks SHALL land before any layout produces an Outline.

### Requirement 4: Room meshes

**User Story:** As a player, I want shaped rooms I can walk around without
falling through or seeing out.

1. A room with an Outline SHALL be built as vertical walls over the Outline with
   a floor and a ceiling meeting them on shared vertices.
2. Its median triangle edge SHALL be in the era band (design finding 1) for its
   race, and a zone's polygon count SHALL stay within the design's cap.
3. Doors SHALL meet corridors flush in position, width, floor height and lintel,
   as they do today.
4. Per-triangle collision (`0x01`) SHALL be unchanged in kind: the walk gate and
   the map outline SHALL read shaped rooms from the mesh with no special case.

### Requirement 5: Three wall styles, as data

**User Story:** As a rule author, I want each style's look written down in a
file I can read, in the same manner as the topology rules.

1. Each Wall_Style SHALL be a TOML file under `rules/walls/`, checked strictly on
   load with failures named by file, field and expected value, as in step 6.
2. A style SHALL set its Cell_Complex, Cell size (in H), Fill band, Relief and
   which shapes each room kind may take.
3. Adding a style SHALL need no code change beyond a Cell_Complex it doesn't
   share with the shipped three.
4. `scripts/topology_rules.py check` SHALL cover the style files, its `draw`
   SHALL show sample Outlines for each style, and `docs/TOPOLOGY_RULES.md` SHALL
   explain them.

### Requirement 6: Styles and shapes in the rules

**User Story:** As a rule author, I want a rule to be able to ask for a shape,
and a theme to choose a style.

1. `rules/topology/themes.toml` SHALL give each theme a Wall_Style.
2. A rule's `shape` SHALL take the values the design lists, with a new default
   `auto` (the style chooses by kind); `rect` SHALL stay and mean a plain Box.
3. Rules that fix a shape (a temple's nave stays a long hall) SHALL do so in the
   shipped sets, as data.

### Requirement 7: Floors and ceilings move

**User Story:** As a player, I want a cave's ceiling to come down and go up, and
its floor to roll a little, with nothing that traps or slides me.

1. `rough` and `hewn` rooms SHALL have Relief as their style sets it.
2. A floor SHALL only rise from `floor_z`, and stay at `floor_z` in every Throat;
   it SHALL pass the walk gate's slope and step limits on the first attempt.
3. A ceiling SHALL only come down from the Box's top, so stacked rooms keep their
   Slab; headroom SHALL stay at least the design's minimum, and above each door's
   lintel in its Throat.
4. A Bridge's slot SHALL keep a flat ceiling around it, so the shaft stays closed.

### Requirement 8: Corridors match

**User Story:** As a player, I don't want a rough cave joined by ruler-straight
hallways.

1. Flat and ramp corridors in a `rough` or `hewn` zone SHALL have their walls
   broken and their ceilings moved, inside their footprint, as their style sets.
2. A corridor's clear width SHALL stay at least the design's minimum, its ends
   SHALL meet the Throats exactly, and its floor SHALL be as built today.
3. Stairs and bridges SHALL stay as built today.

### Requirement 9: Textures follow

1. Each style SHALL name the wall, floor and ceiling look it asks for, so a
   `rough` room gets rock and not coursed masonry, with step 4's texel density
   and Look_Stats bands still holding.
2. Texture coordinates SHALL run continuously round a faceted wall, with no
   visible jump at a bend.

### Requirement 10: Outdoor dungeons

1. An outdoor dungeon with no theme SHALL default to `rough`.
2. The step 5 and 7 guarantees SHALL hold: every room under the hill with the
   Rock_Cover, one Entrance, the Tunnel meeting its room, and every room
   reachable from the Outdoor_Spawn.

### Requirement 11: Controls, sidecar and maps

1. A **Walls** control (From theme, Built, Hewn, Rough) SHALL show for dungeons
   and outdoor dungeons on the Graph layout, and reach the CLI and the server.
2. The sidecar's `layout` block SHALL record the zone's style and each room's
   shape, Fill and Outline points; the side panel SHALL name the style.
3. The map (SVG) SHALL draw a room's Outline in place of its Box. The EQ map
   files and the outline already read walls from the mesh; a test SHALL pin that
   they follow shaped rooms.

### Requirement 12: Like the stock zones, and everything else holds

1. Over many seeds, built zones of each style SHALL measure inside that style's
   survey bands (Req 1) with the survey's own code: Axis_Share, plumb share, Fill,
   Relief and median edge.
2. The three styles SHALL differ in the measured direction: `built` above `hewn`
   above `rough` on Axis_Share, and the reverse on Relief.
3. Classic builds, cities and wilderness SHALL be byte-identical; step 6 and 7's
   shape bands, Stacked_Share and fidelity bars SHALL still hold.
4. Graph builds SHALL pass the gate first try at least as often as step 7's,
   across styles, rule sets, themes, races and Verticality.
5. The same inputs SHALL give byte-identical `.eqg` contents (footer aside).
6. A 14-room build SHALL take at most step 7's build time plus 10 s.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge it, a
   step in `docs/ACCEPTANCE.md` "Step 8 — Room walls".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass: the three styles are obvious at a glance in 3D
   and read as a natural cave, a man-made cave and a dungeon; shaped rooms walk
   cleanly; and nothing shows through a wall.
