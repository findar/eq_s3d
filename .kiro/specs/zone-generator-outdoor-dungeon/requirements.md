# Requirements Document

> **STATUS: roadmap step 5, ready.** Written 2026-11-01. The user answered the
> design's open questions the same day (`archive.md` "Decisions"). Task index:
> `tasks.md` (card format, 14 tasks).

## Introduction

Roadmap step 5: **outdoor dungeons, in the style of Blackburrow and
Mistmoore.** Generate the terrain first, then carve or add the dungeon into
it. Today a zone is either all outdoors (wilderness: an open heightfield) or
all indoors (dungeon and city: rooms joined by corridors in empty space). A
classic outdoor dungeon is both: a compact patch of landscape with a cave
mouth in a hillside (Blackburrow, Runnyeye) or a structure whose halls run
underground (Mistmoore, Unrest), so a player walks from open ground into the
rooms.

Measured on the stock client (design "Research findings"), classic outdoor
dungeons are compact (358–980 u on a side, against our 2400 u wilderness) and
span a lot of height for their size (their upward-facing surfaces spread over
roughly 100–290 u, p10 to p90; roofs included, so task 1 refines it). How much of
their floor is under a roof, and how far below the ground the rooms sit, could
not be measured reliably with a simple overhead test (sky planes and roof
tops confuse it); task 1 measures it properly with a walk from the zone's safe
point.

This step pulls in the architecture runway the roadmap set aside for it (the
retired `zone-generator-followup` spec): a 3D `Envelope` the room layout must
fit inside, and a gate that checks connectors through it.

This spec sits under the umbrella `zone-generator`
(`.kiro/specs/zone-generator/`). "Req X.Y" below means a requirement of THIS
spec unless it says "umbrella".

**Out of step 5:** surface buildings and castles (a later step unless Open
question 1 chooses them), graph-replacement layouts (step 6), multi-level
sections inside the dungeon beyond ramps (step 7), rough cave walls (step 8),
new wilderness ground textures (deferred from step 4), and the in-client check
(M6).

## Glossary

- **Host_Terrain**: the outdoor heightfield of an outdoor-dungeon zone, made by
  the wilderness pipeline at a smaller size, with a Host_Hill.
- **Host_Hill**: the raised landform the dungeon is carved into.
- **Envelope**: the 3D volume the dungeon's rooms and corridors must fit
  inside: under the Host_Hill's surface by at least the Rock_Cover, above a
  floor limit, and within the hill's footprint.
- **Rock_Cover**: the minimum thickness of terrain left above any room or
  corridor ceiling.
- **Entrance**: the passage from open ground into the dungeon: an Apron (a
  flattened, walkable pad on the hill's flank), a Mouth (the opening cut in
  the terrain) and a Tunnel (a corridor from the Mouth to the first room).
- **Outdoor_Spawn**: the safe point, on open ground facing an Entrance.

## Requirements

### Requirement 1: Measure the classic anatomy

**User Story:** As the project owner, I want the stock outdoor dungeons
measured properly, so that size, depth and cover are set from real zones.

1. A survey SHALL walk each listed classic zone's floor from its safe point
   (the WLD walk the traversal agent uses: slope ≤ 40°, step ≤ 3 u) and
   report, for the reachable floor only: zone span, the share of floor area
   under a roof within 250 u, how far covered floor sits below the open floor
   near it, the rock thickness above covered floor where a surface lies above
   it, and the number of Entrances (separate places where open and covered
   floor meet at walking height).
2. The survey's numbers SHALL be written into the design's research findings
   and drive the defaults of Req 3–5.

### Requirement 2: Envelope in the layout

**User Story:** As the project owner, I want the room layout to fit inside a
3D volume, so that a dungeon can be laid out under a hill.

1. `LayoutGenerator.generate` SHALL accept an optional Envelope; with one, every
   room's box and every corridor's swept volume SHALL lie inside it.
2. Without an Envelope the layout SHALL be byte-for-byte what it is today
   (the step 3 UV-free goldens and the layout tests unchanged).
3. IF the requested rooms cannot fit, THEN the generator SHALL place as many as
   fit, never fewer than 3, and record a `rooms_reduced` warning.

### Requirement 3: Host terrain

**User Story:** As a user, I want an outdoor-dungeon zone to have real
landscape around the dungeon, so that it reads like Blackburrow, not a box in a
field.

1. An outdoor-dungeon zone SHALL be a wilderness-style bowl at the Open
   question 2 size, with one Host_Hill large enough to hold the Envelope for
   the requested rooms with the Rock_Cover.
2. The bowl SHALL keep the wilderness guarantees: sealed rim, walkable open
   ground, water and lava handled as today.
3. The Host_Hill's terrain SHALL be unchanged by the dungeon except at the
   Entrance's Apron and Mouth.

### Requirement 4: Entrance

**User Story:** As a player, I want to walk from open ground into the cave
mouth, so that the dungeon is part of the landscape.

1. Each Entrance SHALL have an Apron (flattened to walkable grade and blended
   into the slope), a Mouth (terrain cut so the Tunnel opens onto the Apron
   with no gap a player can fall through or see through around it), and a
   Tunnel that reaches the first room within the corridor grade cap.
2. The Outdoor_Spawn SHALL be on open ground with a walkable path to an Apron.
3. The terrain above the Mouth SHALL keep at least the Rock_Cover over the
   Tunnel.

### Requirement 5: One walkable zone

**User Story:** As a player, I want to reach every room from where I spawn
outdoors.

1. The zone's collision SHALL be one TER holding the Host_Terrain and the
   dungeon mesh.
2. The gate SHALL check, on that TER, that every room is reachable from the
   Outdoor_Spawn through an Entrance, that every corridor is continuous, and
   the wilderness bowl and trunk checks for the open ground.
3. A build that fails SHALL be retried with a fresh seed like any gate failure.

### Requirement 6: Zone type and controls

1. An `outdoor_dungeon` zone type (or the Open question 4 alternative) SHALL be
   selectable from the prompt (words such as "outdoor dungeon", "cave in a
   hill", "barrow", "warren in the hills"), the Controls panel, the CLI and
   the server, and listed as enabled.
2. Room count, theme, race and tint SHALL work as for dungeons; edges and
   trees as for wilderness.
3. The sidecar SHALL record the Envelope bounds, the Rock_Cover, each Entrance
   (Apron centre, Mouth, Tunnel id) and the Outdoor_Spawn.

### Requirement 7: Look and maps

1. Rooms and corridors SHALL use step 4's recipe textures for their theme;
   open ground, water and trees as in wilderness builds.
2. The map outline and EQ map files SHALL show the open ground and the
   dungeon, the dungeon on its own depth band where it lies under the ground.
3. The preview SHALL show both, with the dungeon visible through the Mouth.

### Requirement 8: Existing zone types unchanged; reproducible; quick

1. Dungeon, city and wilderness builds SHALL be unchanged for the same inputs.
2. The same inputs SHALL give byte-identical `.eqg` contents (footer aside).
3. An outdoor-dungeon build SHALL take at most 60 s on the reference machine.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge
   it, a step in `docs/ACCEPTANCE.md` "Step 5 — Outdoor dungeon".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass: the zone reads as a classic outdoor
   dungeon, the Entrance looks carved into the hill with no gaps, and every
   room can be walked to from the spawn. The in-client check is M6.
