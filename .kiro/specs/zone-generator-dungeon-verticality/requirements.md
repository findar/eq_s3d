# Requirements Document

> **STATUS: roadmap step 7, ready.** Written 2026-11-04 at master `8edf1df`;
> the user took the recommended answer to every open question the same day
> (`archive.md` "Decisions"). Task index: `tasks.md` (card format, 17 tasks).

## Introduction

Roadmap step 7: **interesting dungeon verticality.** Today every generated
dungeon is one level. Rooms sit at different heights, but only as far as a
ramp at a gentle grade (0.5) can carry between neighbours; no room is ever
above another, and the only connector is a ramp. The user's step 5 first look
asked for dungeons that go up and down, not only across. Classic EQ
dungeons do: Guk's upper and lower halves, Befallen's levels, Najena's stairs,
Unrest's cellars and upper floors.

Step 6 left the hooks for this step:

- **Vertical relations in the rules.** A rule's edge can say the second room
  is `above` or `below` the first, or `level` with it. Step 6 acts on them
  only by choosing which way a ramp goes.
- **One switch for stacking.** Placement keeps every pair of rooms apart in
  plan through one function, `may_overlap_in_plan`, which always says no.
- **Stairs exist but are never used.** `generators/geometry.py` builds a
  staircase (treads and risers) when a corridor has `steps > 0`, and the walk
  check (`analyzer/traverse.py`) passes a stair whose risers are at most the
  agent's step-up (3 u). No layout asks for one.
- **Maps already split stacked floors.** The EQ map files and the outline
  give each stacked floor its own depth band (step 1b).

This step makes graph dungeons multi-level: rooms that sit above other rooms,
joined by staircases (and, if Open question 1 says so, bridges), driven by the
rules and the Verticality control, checked by a walk gate that knows the new
connectors before any generator makes them (the retired followup runway's F4:
"gate before generator").

This spec sits under the umbrella `zone-generator`
(`.kiro/specs/zone-generator/`). "Req X.Y" below means a requirement of THIS
spec unless it says "umbrella".

**Out of step 7:** room shapes other than rectangles (step 8), what's inside
rooms (step 9), one-way drops and shafts the player falls down (unless Open
question 1 brings them in), the Classic engine (it stays one level), and the
in-client check (M6).

## Glossary

- **Level**: a whole-number height index a grown room gets from the rules'
  vertical relations (`above` = +1, `below` = −1, `level` = 0 relative to its
  neighbour). Level 0 is the entrance's.
- **Level_Height**: the vertical distance between two levels: a room's
  height plus the Slab (floor-to-floor), so a room on level 1 can sit
  directly over one on level 0.
- **Slab**: the solid thickness between a lower room's ceiling and the floor
  of the room above it.
- **Stacked_Pair**: two rooms that overlap in plan, on different levels.
- **Vertical_Connector**: a corridor joining rooms on different levels: a
  Staircase, or a Bridge if Open question 1 includes them.
- **Staircase**: treads and risers, each riser at most the Riser_Cap; straight,
  or a Switchback (two flights and a landing) when the run is short.
- **Riser_Cap**: the largest riser a generated stair uses (below the walk
  agent's 3 u step-up).
- **Bridge**: a walkway that crosses over a lower room or void at height,
  joining two rooms on the same upper level.
- **Stacked_Share**: the share of a dungeon's floor area that has another
  walkable floor directly above it.

## Requirements

### Requirement 1: Measure the stock vertical anatomy

**User Story:** As the project owner, I want the stock dungeons' verticality
measured, so that the levels, stacking and stairs are set from real zones.

1. A survey SHALL walk each listed stock dungeon's floor (the WLD walk step 6's
   survey uses) and report per zone: vertical span (p10–p90 of walked floor
   height), the number of floor levels (height clusters with a meaningful
   share of floor area), the Stacked_Share, the level-to-level height, and
   the steepest connector chains (stairs and steep ramps: rise, run, riser
   height where the treads are distinct).
2. The survey's numbers SHALL be written into the design's research findings
   and set the Level_Height, the Riser_Cap, the rules' vertical weights and
   the bands of Req 6.

### Requirement 2: The gate knows the new connectors first

**User Story:** As a developer, I want the walk gate to understand stairs
(and bridges) before any generator builds them, because in this project
structural tests passing has never been enough.

1. The walk gate SHALL treat a Staircase as walkable when every riser is at
   most the agent's step-up, every tread is long enough to stand on, and the
   headroom over every tread is at least the agent's height; and a Bridge as
   walkable when its deck is continuous, within the slope cap, and joined
   flush to the floors at both ends.
2. A connector that breaks one of these (a riser too tall, a tread too short,
   no headroom, a gap at a landing or a bridge end) SHALL be caught, named in
   the gate's diagnosis, and pinned as a regression example.
3. These checks SHALL land, with property tests over generated connectors,
   before any layout produces stacked rooms.

### Requirement 3: Stair and bridge geometry

**User Story:** As a player, I want stairs I can walk up and down, that look
like stairs.

1. A Vertical_Connector SHALL be built as a Staircase with risers at most the
   Riser_Cap: straight when its leg is long enough, otherwise a Switchback
   whose landing is flush with both flights.
2. Both ends SHALL meet the room floors flush, as ramps do today (the routing
   rule that confines the whole rise to one leg keeps holding).
3. Headroom over every tread and landing SHALL be at least the corridor's
   height less the rise of one riser.
4. WHERE Open question 1 includes bridges, a Bridge SHALL be built as a deck
   at the upper level crossing the lower room's volume, with the lower room's
   ceiling opened under it so the void reads from both levels.

### Requirement 4: Levels in grown layouts

**User Story:** As a user, I want a graph dungeon to have rooms above and
below each other, as the rules ask.

1. The graph engine SHALL give each room a Level from the rules' vertical
   relations, and its floor at that Level's height (plus the small variation
   ramps give today).
2. Two rooms SHALL overlap in plan only when they are on different Levels and
   the Slab between them is at least the design's minimum; every other pair
   stays apart as in step 6 (`may_overlap_in_plan` is the one switch).
3. A corridor SHALL pass over or under a room only with the Slab's clearance;
   the shared layout steps (separation, crossing splits, conflict drops) SHALL
   judge rooms and corridors in 3D, so a corridor under a room is not split
   and a stacked room is not pushed apart.
4. An edge between rooms on different Levels SHALL become a Vertical_Connector;
   an edge within a Level stays a corridor or ramp as today.
5. The Classic engine SHALL be unchanged: one level, byte-identical builds.

### Requirement 5: The rules go up and down

**User Story:** As a rule author, I want rules that take the dungeon down a
level or up a tower, in the same files as today.

1. The shipped rule sets SHALL gain vertical rules (e.g. a descent: a way
   on that drops a level; a stair hall; a gallery over a lower room) written
   as data with the existing format, plus at most one new vertical field if
   the format needs it (design "Rule format").
2. The Verticality control SHALL scale the vertical rules: `flat` keeps every
   room on one level, `moderate` uses the rules' weights, `dramatic` weights
   the vertical rules up.

### Requirement 6: Shape, like the stock zones

1. Over many seeds and room counts, the BUILT graph dungeons' Stacked_Share,
   level count and vertical span SHALL fall inside the survey's bands for
   `moderate`; `flat` SHALL be one level; `dramatic` SHALL be at or above
   `moderate` on each.
2. The step 6 shape bands (dead ends, loops, deep end) and Edge_Fidelity bars
   SHALL still hold.

### Requirement 7: Outdoor dungeons go down

**User Story:** As a user, I want an outdoor dungeon to go down into the
hill, not only across under it.

1. An outdoor dungeon SHALL honour the Verticality control and use more than
   one Level where its Envelope allows, with the Tunnel entering at the top
   Level.
2. The step 5 guarantees SHALL hold: every room under the hill with the
   Rock_Cover, one Entrance, every room reachable from the Outdoor_Spawn.

### Requirement 8: Controls, sidecar and maps

1. The Verticality control SHALL show for graph dungeons and outdoor dungeons.
2. The sidecar's `layout` block SHALL record each room's Level, each
   Vertical_Connector (kind, rise, risers, switchback or not), and the
   Stacked_Share.
3. The EQ map files and the outline SHALL show each Level on its own depth
   band where it is stacked (existing behaviour, pinned by a test on a
   stacked build).

### Requirement 9: Everything else holds

1. Classic builds, city, wilderness and the step 6 graph builds at `flat`
   behave as today (the classic goldens unchanged).
2. Graph builds SHALL pass the walk gate on the first attempt at least as
   often as step 6's, across both rule sets, the themes and the races.
3. The same inputs SHALL give byte-identical `.eqg` contents (footer aside).
4. A multi-level build SHALL take at most the step 6 graph build's time plus
   10 s on the reference machine.

### Requirement 10: Rooms sized for their builders

**User Story:** As a user, I want a dungeon's rooms to fit the race that made
it: an ogre never builds small rooms, dragons need vast halls, and a human
wouldn't build a dragon's.

1. Each dungeon race SHALL have a measured body height, taken from its
   character model in the client files where possible (design finding 8),
   the default (human) race included; `dragon` SHALL join the races.
2. Each race SHALL have a room-height band (a minimum and a maximum, from its
   body height) and a footprint band; every room's size class SHALL fall
   inside its race's bands, so a race's smallest room is still sized for it
   and its largest stops at the race's maximum.
3. Both engines SHALL use the bands (the Classic engine already scales by
   race); the Level_Height (Req 4) SHALL follow from the banded room heights.
4. A build with no race SHALL use the default race's bands; builds whose
   sizes change because of the bands (raced builds of either engine) SHALL
   say so in the commit that changes them, with the old and new goldens.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge
   it, a step in `docs/ACCEPTANCE.md` "Step 7 — Dungeon verticality".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass: graph dungeons with stairs between stacked
   rooms read like classic multi-level dungeons, the stairs look and walk
   right both ways, and every room can be walked to.
