# Requirements Document

> **STATUS: roadmap step 11, ready.** Written 2026-11-08 at master `e50ecfc`; revised the same
> day for the user's direction to use the client's own models, catalogued and tagged (design
> decision 1). Every open question answered the same day (`archive.md` "Decisions"). Task index:
> `tasks.md` (card format, 17 tasks).

## Introduction

Roadmap step 11: **decorating rooms.** A generated room today has a shape (step 8), a kind
(step 6), structure built into its mesh (step 9: daises, pillars, plinths, boulders) and
advisory POIs. Nothing is placed in it. Its `prop_hints` ("raised throne dais", "weapon racks")
are words in the side panel.

Stock rooms are full. A probe of the placed objects of 15 Classic dungeons and 15 cities
(design finding 1) counts 12,501 objects: 7–48 per room in dungeons, median about 19. In
dungeons a third are debris (rocks, bones, webs, mushrooms) and nearly a third are lights
(torches, lanterns, braziers); furniture and containers are a tenth each. Cities hold more
furniture (23%) and more lights (37%). Each culture has its own set: Paw's hooks and tables,
Guk's lanterns and planks, Sebilis's shackles, Kurn's bunks and crates.

**The models come from the client** (design decision 1). Generated props would be hard to keep
in line with EverQuest's look, so this step uses the stock models. A Classic zone keeps its
models in its own `<zone>_obj.s3d` and names them from the placements in `<zone>.s3d`; no zone
can borrow another's by name (design finding 0). So a build copies the models it uses into
its own `.eqg`, as stock zones carry their own copies. To choose among the 4,408 stock models,
this step first **catalogues every one of them** (measured, where stock placed it, and tagged)
and has the tags reviewed by a person.

Then it puts **Props** in rooms: catalogued models of torches, tables, chairs, beds, barrels,
crates, chests, bones and banners, placed as ZON objects. What a room gets comes from its room
type, its race and theme, and its Clutter Scale. Props stand on the floor, hang on walls or
from the ceiling, never block the way through, and dress the room's POIs: a throne on the boss
dais, candles by an altar, chests by the treasure.

Earlier steps left these hooks:

- **Placed models as ZON objects** (steps 2 and 10), and the Footprint gate
  (`analyzer/footprints.py`) judging placed models from their own collidable triangles.
- **Stock model reading** (`core/wld.py`, `scripts/site_survey.py`): meshes, flags, UVs and
  texture names from `_obj.s3d`, and per-model measures.
- **The Spine** (step 9, `generators/room_layouts.py`), Features and POIs per room.
- **Scales** (step 9, `rules/rooms/scales.toml`): Clutter, whose comment already says "loose
  objects in step 11", and Finish.
- **One light per room** (`generators/layout.py`), at its centre.

This spec sits under the umbrella `zone-generator` (`.kiro/specs/zone-generator/`). "Req X.Y"
below means a requirement of THIS spec unless it says "umbrella".

**Out of step 11:** generated Props (a follow-up where the catalogue lacks a kind); later-era
`.eqg` models; animated models (flags, moving flames, gears); doors and door records (the SQL
export, M6); NPC spawns (M6); climbable props (ladders); interactive objects; new room
geometry; and the in-client check (M6).

## Glossary

- **Catalogue**: one entry per distinct stock model in the install's `_obj*.s3d` archives, with
  measured fields, observed placements and Tags. Metadata only; the mesh stays in the install.
- **Tag**: a catalogue field naming what a model is and where it goes: Category, kind, Mount,
  Set, era, collision, suits, `use`. Proposed by the auto-tagger with a confidence; a reviewed
  Tag wins.
- **Review sheet**: a local HTML contact sheet of catalogue entries with thumbnails, measures,
  placements and Tags, for a person to check.
- **Prop**: one catalogued model placed in a room or a Site, as a ZON object.
- **Category**: light, furniture, container, debris or hanging (design finding 1).
- **Mount**: where a Prop attaches: floor, wall (at a height on a wall face) or ceiling.
- **Set**: the culture a model belongs to (gnoll, goblin, dark elf, human city, neutral),
  from its name prefix, its zones and review.
- **Group**: Props placed together as one: a table with chairs, a row of bunks, a crate pile.
- **Decor_Recipe**: the data saying which Props and Groups a room gets, by Tag, and how they're
  arranged, by room type, kind, race and theme.
- **Dressing**: Props a POI asks for: a throne at a boss POI, candles at an altar.
- **Footprint, Spine, POI, Scale, Weights, Layer**: as steps 9 and 10.

## Requirements

### Requirement 1: Catalogue and measure the stock models

**User Story:** As the project owner, I want every stock model catalogued as it exists, so
that Props are chosen from what EverQuest already has.

1. A catalogue SHALL hold one entry for every distinct actor model in every `_obj*.s3d` in the
   install: same name and mesh is one entry, same name with a different mesh is a variant.
2. Each entry SHALL record its source, triangles, plan size, height, depth below origin,
   collidable share, walk-in, textures, and whether it is animated.
3. Each entry SHALL record how stock places it: zones and counts, zone type, height over the
   floor, distance to the nearest wall, under a ceiling or not, scale.
4. For the dungeons and cities of finding 1, a survey SHALL report per zone and room style
   Props per room and per 1000 u² of floor, Category shares, Mount shares, lights' spacing
   along walls, and Groups.
5. The catalogue and survey SHALL say what they can't read: models that fail to parse, names
   with no model, and rooms the split joined.

### Requirement 2: The gate knows Props first

**User Story:** As a player, I want every room to stay walkable, so that no table or crate
pile shuts a door.

1. Before any generator places a Prop in a room-graph build, the walk gate SHALL judge placed
   models in dungeon, city and outdoor-dungeon builds from the models' own collidable
   triangles, closed meshes or not: a Footprint that cuts reached floor from the entrance, a
   door or Throat narrowed below the clear width, and a POI not reached SHALL each fail, named.
2. With no placed models the gate SHALL give the same answer as today on every build.

### Requirement 3: Tags, reviewed

**User Story:** As the project owner, I want every model tagged, and the tags that matter
checked by a person, so that a chair is used as a chair.

1. An auto-tagger SHALL propose every Tag of every entry, from its name, its geometry and its
   observed placements, each with a confidence.
2. Reviewed Tags SHALL live in a checked file keyed by catalogue entry, SHALL win over
   proposed ones, and SHALL survive rebuilding the catalogue.
3. A review sheet SHALL show each entry's thumbnail, measures, placements and Tags, grouped by
   proposed kind, lowest confidence first; it SHALL stay local.
4. A model SHALL enter builds only with `use = yes`.

### Requirement 4: Importing a model

1. A catalogued model SHALL be converted to a `.mod` with its textures as DDS, its vertices,
   triangles, UVs and passable flags unchanged.
2. The import SHALL read from the install at build time, once per model in use per build.
3. Imported models SHALL round-trip through the `.mod` writer and reader exactly.

### Requirement 5: Sets

1. A room SHALL take its Props from the Sets its race, theme and zone type name, filling in
   from neutral models; Props of two cultures SHALL NOT share a room unless a Set allows it.

### Requirement 6: Placement keeps the room open

**User Story:** As a player, I want Props where someone would put them, never in the way.

1. Floor Props SHALL stand on reached floor, off the Spine and every Throat, off Features
   (except where a recipe puts them on a dais), inside the room.
2. Wall Props SHALL stand against a wall face at the height stock uses for that model, and
   never across a door opening; ceiling Props SHALL hang only where the ceiling is above their
   bottom plus head height.
3. A Group SHALL be placed whole or dropped whole; a Prop or Group that can't fit SHALL be
   dropped and recorded, never fail the build.
4. Placement SHALL draw from its own salted random stream, so geometry is identical whatever
   the Props, and with Decor `none` every build is byte-identical to step 10.

### Requirement 7: Decor recipes, as data

1. Decor_Recipes and Sets SHALL be TOML under `rules/decor/`, checked strictly on load, every
   bad value named by file, entry and field.
2. A Decor_Recipe SHALL ask for Props by Tag, with arrangement, count, chance and the Scale that
   moves them; its lookup SHALL follow step 9's (room type, else kind, else default).
3. Every Tag a recipe asks for SHALL have at least one `use = yes` model, or the check SHALL
   name the line.
4. How many Props a room gets SHALL come from Weights by Layer (default, zone type, race, theme,
   room kind or type, control), with Clutter moving debris, set from finding 1.

### Requirement 8: POIs are dressed

1. A POI SHALL name the Dressing it asks for (boss: a throne or a seat; altar: candles or
   braziers; treasure: chests; guard: a stool and a torch), placed before the room's other
   Props.
2. Every POI SHALL stay on reached floor; Dressing SHALL never stand on the POI's own spot.
3. A room's `prop_hints` SHALL list what was placed where a Tag exists for a hint, and keep the
   word where none does.

### Requirement 9: Lights

1. Each light-bearing Prop SHALL add a ZON point light at its flame, and the room's own light
   SHALL stay.

### Requirement 10: Controls, sidecar and maps

1. A **Decor** control (None, Sparse, Normal, Dense; default Normal) SHALL exist on the web page,
   the CLI and the plan; prompt words ("cluttered", "bare", "furnished") SHALL choose it in the
   rule planner.
2. A **decor seed** SHALL reroll a zone's Props and nothing else; the page SHALL offer it on a
   built zone.
3. The sidecar SHALL list each room's Props (catalogue entry, kind, position, yaw, Mount), its
   Dressing by POI, and what dropped and why.
4. The EQ map SHALL draw floor Props' Footprints; the web map SHALL show them.
5. Umbrella Reqs 32.4 and 32.7 SHALL be refined: room-graph builds may pack catalogued stock
   models copied unchanged from the user's install, their textures, and one ZON object per
   Prop; every other mesh is still generated.
6. Without the install, Decor SHALL fall back to `none` with a warning.

### Requirement 11: Site Props

1. A Site's POIs SHALL be dressed by the same path (haybales and a cart at a farmstead, crates
   at a camp), with every step 10 guarantee holding.

### Requirement 12: Like the stock zones, and everything else holds

1. Over many seeds at Normal, built rooms SHALL measure inside the survey's bands for Props per
   room, Category shares and Mount shares, with the survey's own code.
2. Every build with Decor `none` SHALL be byte-identical to step 10. The gate's first-try rate
   SHALL hold.
3. The same inputs and install SHALL give byte-identical `.eqg` contents (footer aside).
4. A build SHALL take at most step 10's time plus 5 s.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge it, a step in
   `docs/ACCEPTANCE.md` "Step 11 — Decorating rooms".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off the tag review and a human pass: rooms read as what they are (a
   barracks, a shrine, a storeroom, a throne room), each room's Props belong to one culture,
   and nothing blocks the way.
