# Requirements Document

> **STATUS: roadmap step 11, DRAFT.** Written 2026-11-08 at master `e50ecfc`. The design's
> open questions wait for the user's answers (`design.md` "Open questions"). Task index:
> `tasks.md` (card format, 15 tasks).

## Introduction

Roadmap step 11: **decorating rooms.** A generated room today has a shape (step 8), a kind
(step 6), structure built into its mesh (step 9: daises, pillars, plinths, boulders) and
advisory POIs. Nothing is placed in it. Its `prop_hints` ("raised throne dais", "weapon racks")
are words in the side panel.

Stock rooms are full. A probe of the placed objects of 15 Classic dungeons and 15 cities
(design finding 1) counts 12,501 objects: 7–48 per room in dungeons, median about 19. In
dungeons a third are debris (rocks, bones, webs, mushrooms) and nearly a third are lights
(torches, lanterns, braziers); furniture and containers are a tenth each. Cities hold more
furniture (23%) and more lights (37%). Each race has its own set: Paw's hooks and tables,
Guk's lanterns and planks, Sebilis's shackles, Kurn's bunks and crates. Step 9 drew the line:
"what fills a stock room is placed objects", and left them here.

This step puts **Props** in rooms: generated models of torches, tables, chairs, beds, barrels,
crates, chests, bones and banners, placed as ZON objects. What a room gets comes from its
room type, its race and theme, and its Clutter Scale. Props stand on the floor, hang on walls
or from the ceiling, never block the way through, and dress the room's POIs: a throne on the
boss dais, candles by an altar, chests by the treasure.

Earlier steps left these hooks:

- **Generated models as ZON objects** (steps 2 and 10): tree and Structure models packed in
  the `.eqg`, one ZON object each; the Footprint gate (`analyzer/footprints.py`) judging placed
  models from their own collidable triangles.
- **The Spine** (step 9, `generators/room_layouts.py`): the floor that must stay clear in a
  room, and Features with their footprints.
- **Scales** (step 9, `rules/rooms/scales.toml`): Clutter, whose comment already says "loose
  objects in step 11", and Finish.
- **POIs** (steps 9 and 10): boss, treasure, altar, guard in rooms; a hut interior and a
  `Light_Spot` at a camp fire in Sites.
- **One light per room** (`generators/layout.py`), at its centre.

This spec sits under the umbrella `zone-generator` (`.kiro/specs/zone-generator/`). "Req X.Y"
below means a requirement of THIS spec unless it says "umbrella".

**Out of step 11:** doors and door records (the SQL export, M6); NPC spawns (M6); animated
objects (flags, flames that move, turning gears); climbable props (ladders); interactive
objects (levers, chests that open); new room geometry (step 9's Features are unchanged);
wilderness ground textures (umbrella Req 16, still deferred); and the in-client check (M6).

## Glossary

- **Prop**: one generated model placed in a room or a Site: a torch, table, barrel, bone pile.
  Placed as a ZON object, like a tree or a Structure.
- **Prop_Kind**: a kind of Prop (`wall_torch`, `table`, `chair`, `barrel`), with its size,
  Mount, collision and variants.
- **Category**: light, furniture, container, debris or hanging (design finding 1).
- **Mount**: where a Prop attaches: floor, wall (at a height on a wall face) or ceiling
  (hanging below it).
- **Group**: Props placed together as one: a table with chairs round it, a row of bunks, a
  pile of crates, a torch pair beside a door.
- **Decor_Recipe**: the data saying which Props and Groups a room gets and how they're
  arranged (along walls, in corners, round a POI, in rows, scattered), by room type, kind,
  race and theme.
- **Material_Set**: the textures a race or theme builds its Props from (rough timber and hide
  for gnolls, dressed wood and iron for a fortress, bone for a tomb).
- **Dressing**: Props a POI asks for: a throne at a boss POI, candles at an altar.
- **Footprint, Spine, POI, Scale, Weights, Layer**: as steps 9 and 10.

## Requirements

### Requirement 1: Measure what fills stock rooms

**User Story:** As the project owner, I want stock room contents measured, so that how many
Props, which kinds and where come from real zones.

1. A survey SHALL assign each placed object of the Classic dungeons and cities of design
   finding 1 to a room (or a corridor), and report per zone and room style: Props per room and
   per 1000 u² of floor, the share by Category, and the share by Mount (from height over the
   floor and distance to a wall).
2. It SHALL measure how Props stand: distance to the nearest wall, lights' spacing along a wall,
   Groups (chairs within reach of a table, rows of beds), and which kinds sit near a door.
3. It SHALL measure each common stock Prop model: triangles, plan size, height, collidable
   share, and texel density.
4. It SHALL say what it can't see: objects it can't name, rooms the split joined, and meaning
   it can't read from names alone.
5. The numbers SHALL set the bands of Req 10 and the densities of Req 6.

### Requirement 2: The gate knows Props first

**User Story:** As a player, I want every room to stay walkable, so that no table or crate
pile shuts a door.

1. Before any generator places a Prop in a room-graph build, the walk gate SHALL judge placed
   models in dungeon, city and outdoor-dungeon builds from the models' own collidable
   triangles: a Footprint that cuts reached floor from the entrance, a door or Throat narrowed
   below the clear width, and a POI not reached SHALL each fail, named.
2. With no placed models the gate SHALL give the same answer as today on every build.

### Requirement 3: Prop models

**User Story:** As the project owner, I want Props that read as Classic-era objects, so that a
room looks lived in.

1. Each Prop SHALL be a generated model (no mesh file read, umbrella Req 32.7), at the stock
   triangle counts of finding 1, closed where it's solid, its origin at its Mount point.
2. Props a player would walk round (furniture, containers, braziers) SHALL be solid; Props a
   player would walk over or under (rugs, low debris, webs, hangings above head height) SHALL
   carry `FLAG_PASSABLE`.
3. A Prop_Kind SHALL have at least one variant, and a Material_Set SHALL change its textures
   without changing its shape.
4. Models SHALL round-trip through the `.mod` writer and reader exactly.

### Requirement 4: Prop textures

1. Materials SHALL be procedural textures (wood, rough timber, iron, cloth, hide, bone, stone,
   ceramic, flame) at the measured texel density, grouped into Material_Sets by race and theme.

### Requirement 5: Placement keeps the room open

**User Story:** As a player, I want Props where someone would put them, never in the way.

1. Floor Props SHALL stand on reached floor, off the Spine and every Throat, off Features
   (except where a recipe puts them on a dais), inside the room.
2. Wall Props SHALL stand against a wall face at their recipe's height, and never across a
   door opening; ceiling Props SHALL hang only where the ceiling is above their bottom plus head
   height.
3. A Group SHALL be placed whole or dropped whole; a Prop or Group that can't fit SHALL be
   dropped and recorded, never fail the build.
4. Placement SHALL draw from its own salted random stream, so geometry is identical whatever
   the Props, and with Decor `none` every build is byte-identical to step 10.

### Requirement 6: Decor recipes, as data

**User Story:** As the project owner, I want decor described in data, so that new kinds,
races and rooms don't need code.

1. Prop_Kinds, Decor_Recipes and Material_Sets SHALL be TOML under `rules/decor/`, checked
   strictly on load, every bad value named by file, entry and field.
2. A Decor_Recipe SHALL name its Props or Groups, their arrangement, count and chance, and the
   Scale that moves them; its lookup SHALL follow step 9's (room type, else kind, else default).
3. How many Props a room gets SHALL come from Weights by Layer (default, zone type, race,
   theme, room kind or type, control), with Clutter moving debris and Finish moving how worked the Props
   are, set from finding 1.

### Requirement 7: POIs are dressed

1. A POI SHALL name the Dressing it asks for (boss: a throne or a seat; altar: candles or
   braziers; treasure: chests; guard: a stool and a torch), and Dressing SHALL be placed before
   the room's other Props.
2. Every POI SHALL stay on reached floor; Dressing SHALL never stand on the POI's own spot.
3. A room's `prop_hints` SHALL list what was placed where a Prop_Kind exists for a hint, and
   keep the word where none does.

### Requirement 8: Lights

1. Each light-bearing Prop (torch, lantern, brazier, candle) SHALL add a ZON point light at its
   flame, coloured by its kind, and the room's own light SHALL stay.

### Requirement 9: Controls, sidecar and maps

1. A **Decor** control (None, Sparse, Normal, Dense; default Normal) SHALL exist on the web page,
   the CLI and the plan; prompt words ("cluttered", "bare", "furnished") SHALL choose it in the
   rule planner.
2. A **decor seed** SHALL reroll a zone's Props and nothing else; the page SHALL offer it on a
   built zone.
3. The sidecar SHALL list each room's Props (kind, position, yaw, Mount), its Dressing by POI,
   and what dropped and why.
4. The EQ map SHALL draw floor Props' Footprints; the web map SHALL show them.
5. Umbrella Req 32.4 SHALL be refined once more: room-graph builds may pack generated Prop
   models (`prop_<kind>_<variant>_<set>.mod`), their textures, and one ZON object per Prop.

### Requirement 10: Site Props

1. A Site's POIs SHALL be dressed by the same path: haybales and a cart at a farmstead, bedrolls
   and crates at a camp, offerings at a shrine, with every step 10 guarantee holding.

### Requirement 11: Like the stock zones, and everything else holds

1. Over many seeds at Normal, built rooms SHALL measure inside the survey's bands for Props per
   room, Category shares and Mount shares, with the survey's own code.
2. Every build with Decor `none` SHALL be byte-identical to step 10. The gate's first-try rate
   SHALL hold.
3. The same inputs SHALL give byte-identical `.eqg` contents (footer aside).
4. A build SHALL take at most step 10's time plus 5 s.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge it, a step in
   `docs/ACCEPTANCE.md` "Step 11 — Decorating rooms".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass: rooms read as what they are (a barracks, a shrine, a
   storeroom, a throne room), the Props look Classic-era and belong to their race, and nothing
   blocks the way.
