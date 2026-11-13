# Requirements Document

> **STATUS: roadmap step 12, ready.** Written 2026-11-12 at master `ad392b8`; the design's
> open questions were answered the same day (`archive.md` "Decisions"; question 5 added
> Requirement 9 and task 19). Task index: `tasks.md` (card
> format).

## Introduction

Roadmap step 12: **World Sockets.** The user's aim (2026-11-08):

> "my ultimate goal is for the model placement in rooms to be independent of room generation,
> such that we optionally generate the world with potential points for dungeon or rooms, then
> generate the rooms to attach to that point, then generate the model placement in a room. is
> there a good way we could isolate these things to make them easy to test so our test
> iterations don't take so long ?"

Step 11 built the last hand-off: rooms -> decor, through the RoomContext
(`generators/room_context.py`), a recorded room corpus (`tests/fixtures/rooms/`) and decor
tests that run on it without building a zone (room-decor decision 15). This step builds the
first hand-off, **world -> Socket -> rooms and Sites**, and makes the stages separate, seeded
on their own and saved, so each can be rerun or tested alone.

Today one seed drives everything and the stages are tangled (design "Today's pipeline"):

- `ai/expand.plan_to_spec` makes the world and the rooms in one call. For an outdoor dungeon,
  `outdoor_dungeon.outdoor_dungeon_spec` builds the whole host TER only to plan the dungeon
  (Envelope, layout, Entrance) and throws it away; `ZoneBuilder.build` builds it again.
- The dungeon's way in (Tunnel, Mouth, Apron) is chosen after its rooms are laid out, from the
  host spec and its TER, and the Apron digs the terrain.
- Sites pick their spots during the build (`wilderness.build.sites_for` -> `place_sites`) from
  the landscape and the built TER, after the dungeon has dug its Apron.
- The layout uses the same seed as the terrain, so rooms can't be rerolled on the same world.
  A decor reroll (`decor_seed`) re-runs the planner, the whole build and the gate.
- Tests that need a hill, a Site or a room build a zone, and most run the gate. The full suite
  took 53.5 minutes at `ad392b8`, almost all of it in gate sweeps (design finding 2).

This spec sits under the umbrella `zone-generator` (`.kiro/specs/zone-generator/`). "Req X.Y"
below means a requirement of THIS spec unless it says "umbrella".

**Out of step 12:** multi-zone worlds and zone lines between zones; more than one dungeon in a
world; door Sockets (a city building's entrance, a Site Structure's interior); the M4 feedback
loop (Sessions, edits, partial rebuild of one room); M3 districts; the M6 SQL export, doors
and spawns; a contents seed for step 9's Features; and any change to what a zone looks like.

## Glossary

- **Stage**: one step of making a zone, run from its inputs and its own seed: **World**,
  **Attach**, **Build**, **Decor**, then **Pack** (ZON, `.eqg`, GLB, sidecar) and the gate.
- **Hand-off**: the versioned JSON a stage writes and the next stage reads.
- **World**: the World stage's result: the terrain grid (heights, cell types, masks) or none,
  the water level, regions, Spawn, and the Sockets it offers. Saved as a World file.
- **Socket**: a typed attach point a World offers: an id, a kind, a position, a facing, an
  opening, a Level, what it accepts, and the ground it sits in.
- **Socket kinds**: `root` (a dungeon or city with no world around it), `hillside` (a
  Host_Hill a dungeon goes under), `ground` (open ground Sites stand on); `door` is reserved
  for later (design question 3).
- **Attachment**: what the Attach stage builds on one Socket and hands on: a dungeon's layout
  and, on a hillside, its Entrance (Tunnel, Mouth, Apron); a Site placement on ground.
- **Terrain edit**: a change an Attachment makes to the World's terrain (today only the
  Apron), applied by the Build stage and seen by every Socket attached after it.
- **Stage seed**: the seed one stage draws from: `seed` (the World, and the default of the
  others), `rooms_seed` (Attach) and `decor_seed` (Decor).
- **World corpus**: World files recorded from pinned seeds, kept as test fixtures.
- **Envelope, Entrance, Apron, Tunnel, Mouth, Host_Hill, Site, RoomContext, room corpus**: as
  steps 5, 10 and 11.

## Requirements

### Requirement 1: The Socket

**User Story:** As the project owner, I want the world to say where things can attach, so
that rooms and Sites are built off a point rather than off the whole zone.

1. A Socket SHALL be plain data with a versioned JSON form: id, kind, position (x, y, z),
   facing (yaw, and side where it has one), opening (width, height), Level, what it accepts,
   and its ground.
2. A `hillside` Socket SHALL carry the Host_Hill's footprint, its surface (the terrain grid
   under it), the Rock_Cover, the entry point and the height of the open ground there, the
   approach side, and the cells the Apron may never dig, so that a dungeon can be laid out and
   its Entrance chosen from the Socket alone.
3. A `ground` Socket SHALL name the World's playable ground and Spawn, and carry the Kept_Clear
   shapes earlier Attachments add, so that Sites can be placed from the World and the Socket
   alone.
4. A `root` Socket SHALL carry no terrain; a dungeon or city attached to it is laid out as
   today.
5. The JSON form SHALL keep every number the Attach stage reads exactly (no rounding), so an
   Attachment made from a saved Socket equals one made from the live Socket.

### Requirement 2: The World stage

**User Story:** As the project owner, I want the world made on its own, so that it can be
rebuilt, tested and kept while what attaches to it changes.

1. The World stage SHALL make a World from the zone type, the World's own inputs (seed,
   biome, edges, zone size, the Socket requests such as a Host_Hill) and nothing else; room
   count, theme, race, tint, verticality, Sites and Decor SHALL NOT reach it.
2. A wilderness World SHALL offer one `ground` Socket; an outdoor-dungeon World one
   `hillside` and one `ground`; a dungeon or city World one `root`.
3. The same inputs SHALL give the same World, equal as JSON text.
4. An outdoor dungeon's host terrain SHALL be made once per build.

### Requirement 3: The Attach stage

**User Story:** As the project owner, I want rooms and Sites built off a Socket, so that the
rooms stage runs and is tested without making terrain.

1. A dungeon on a `hillside` Socket SHALL be laid out, fitted and given its Entrance from the
   Socket, the plan's room fields and `rooms_seed` alone; its Envelope's floor limit comes from
   its own verticality and race.
2. Sites on a `ground` Socket SHALL be placed from the World, the Socket, the Sites controls
   and `rooms_seed` alone.
3. Sockets SHALL be attached in a fixed order (hillside before ground); an Attachment's
   Terrain edits and Kept_Clear shapes SHALL be applied to what every later Socket sees.
4. A dungeon or city on a `root` Socket SHALL be laid out as today.
5. An Attachment that can't be made SHALL fail as a planning failure the pipeline retries
   (`PLAN_ERRORS` today), named by Socket.

### Requirement 4: Stage seeds and rerolls

**User Story:** As a user, I want to reroll the rooms on a world I like, as I can reroll its
Props.

1. A `rooms_seed` SHALL exist on the plan, the CLI and the web page; unset, it is the zone's
   seed.
2. A build with a new `rooms_seed` and the same seed SHALL keep the World: the same World
   file, and the same terrain heights everywhere outside the new Attachments' Terrain edits.
3. The page SHALL offer "Reroll rooms" on a built zone, as it offers "Reroll decor".
4. The sidecar SHALL record every stage seed the build used.
5. A `decor_seed` SHALL keep its step 11 meaning.

### Requirement 5: Saved hand-offs

**User Story:** As the project owner, I want each stage's result saved, so that I can look at
one stage and rerun the next from it.

1. Every build SHALL write its World, its Attachments and the RoomContexts it made (none with
   Decor `none`) as versioned JSON in its build directory, beside the other artifacts.
2. Each stage SHALL be deterministic: the same hand-off and stage seed give the same result,
   equal as JSON text.
3. A hand-off of another version SHALL be refused on read, naming the file and both versions.
4. A command SHALL run one stage from the previous stage's hand-off file and write its own,
   with a GLB of that stage's result (the terrain with its Sockets marked, the attached rooms
   alone, or the decorated rooms), in seconds.
5. Rerolls SHALL re-derive the earlier stages from their seeds, not read hand-off files back
   (design question 6).

### Requirement 6: Bytes stay the same

1. With no stage seed set, every build SHALL be byte-identical to step 11 (`.eqg` contents,
   footer aside), and its Zone_Spec JSON SHALL be unchanged: the goldens in
   `tests/test_layout_engine.py`, the Decor and Site goldens, and the room corpus.
2. A change the user chooses that moves bytes (design questions 1, 2 and 7) SHALL be one
   deliberate recapture, named in its commit and in `archive.md`.
3. The sidecar MAY gain blocks (`sockets`, `seeds`); no existing key changes meaning.

### Requirement 7: Testing in isolation

**User Story:** As the project owner, I want each stage tested on its own, so that test
iterations take minutes, not most of an hour.

1. A recorder SHALL save a World corpus from pinned seeds covering every biome, every approach
   side, water and no water, and every Socket kind.
2. Attach tests (outdoor-dungeon planning, Entrance, Sites) SHALL run on the World corpus
   without making terrain, building a TER or running the zone gate.
3. One `slow` contract test SHALL check that the World corpus still matches the World stage,
   and one that an Attachment from a saved Socket equals one from the live Socket; when a stage
   changes on purpose, its corpus is re-recorded.
4. The Attach stage SHALL check its own result (rooms inside the Envelope, the Tunnel covered
   and within grade, every Site's rules) without the zone gate; the zone gate stays in a few
   integration builds per zone type.
5. The fast suite (`-m "not slow"`) and the full suite SHALL meet the time targets design
   finding 2 sets, measured with `--durations`.

### Requirement 8: Corridor contexts (design question 7, answered yes)

1. The Build stage SHALL hand decor a RoomContext per corridor (`source = "corridor"`), so
   corridor lights are placed by the path step 11 built.
2. Builds with Decor `none` SHALL be unchanged; Decor-on goldens and bands are recaptured once.

### Requirement 9: A gate failure rerolls only the failing stage (design question 5, answered yes)

**User Story:** As a user, when a random build fails the gate because of its rooms or its
Props, I want the retry to keep the world it drew and reroll only what failed.

1. On a gated zone type with a random seed, a rejected attempt SHALL be retried from the stage
   the gate's report names: Decor (redraw `decor_seed`) or the rooms (redraw `rooms_seed`),
   keeping every earlier stage's seed.
2. When the stage can't be named, or after two stage rerolls on one World, the retry SHALL
   draw a fresh `seed` for everything, as today.
3. Pinned seeds SHALL fail as they do today; retries stay inside the attempt cap and timeout.
4. Each rejected attempt's log line SHALL name the stage blamed and the seeds it used.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge it, a step in
   `docs/ACCEPTANCE.md` "Step 12 — World Sockets".
2. The fast and thorough suites are green, inside Req 7.5's targets; the frontend builds.
3. The user signs off a first look and an acceptance pass: zones look as they did, rooms
   reroll on the same world, Sockets show on the map, and the stage commands give a
   one-stage loop of seconds.
