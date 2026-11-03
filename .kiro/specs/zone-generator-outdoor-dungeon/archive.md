# Archive — zone-generator-outdoor-dungeon

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 14).

## Decisions

The design's "Decisions" section (1–4) stands. The user answered its open
questions on 2026-11-01, each with the recommended option:

- **Archetype (Open question 1):** a hillside cave (Blackburrow, Runnyeye):
  rooms and tunnels under a hill, a cave mouth in its flank.
- **Size (Open question 2):** compact, about 1200 u square.
- **Entrances (Open question 3):** one.
- **Selection (Open question 4):** a new `outdoor_dungeon` zone type.
- **Connectors (Open question 5):** ramps only; staircases and the gate
  learning rise/run and headroom come with step 7.
- **Host terrain is a Landform (task 3, 2026-11-02):** the matrix takes a
  `Landform` (kind `hill` or `pit`, footprint radius, signed relief, flank,
  approach side) and gives interior plains cells a soft `relief` offset;
  synth only adds it to the base. New outdoor-dungeon archetypes (a pit like
  Blackburrow's, later others) add a kind, not a node type or a synth path.
  A Landform backs onto a mountain side and tapers away from zonelines and
  water (frozen flat cells it would otherwise meet in a cliff).
- **Envelope from the TER (task 4, 2026-11-02):** `outdoor_dungeon.host_envelope`
  interpolates the built TER, footprint a disc to the hill's half-relief
  (radius + flank / 2), floor limit 150 u under the approach foot's height
  until task 5 passes the real Entrance floor. Rooms under a hill are 80 u
  tall and sized to the Envelope (`layout_in_envelope`); `_fit_floors`
  shifts the layout by its tightest room's headroom, not to the entrance's
  band top, so the entrance room is not always the highest.
- **Entrance on the terrain grid (task 5, 2026-11-02):** the Tunnel is one
  terrain cell wide (between two vertex columns) and ends at a vertex row;
  the Mouth replaces the one cell in front of the portal with a floor, two
  jambs and a headwall on the terrain's own vertices, so it stitches
  exactly. The Apron is a trench dug down to a 0.5-grade cone, kept off the
  Rim, zonelines and water. `plan_entrance` picks the least digging;
  `build_outdoor_ter` returns the one merged TER task 6 builds on.
- **An outdoor dungeon is a wilderness spec with a dungeon (task 6,
  2026-11-02):** `outdoor_dungeon_spec` returns the host wilderness spec
  carrying the rooms, corridors and materials, with a `dungeon` section in
  the wilderness payload (Entrance, cover, floor limit, warnings).
  `TerrainBackend` builds it when that section is present; the pipeline
  gates it with `outdoor_dungeon_report` and retries `PLAN_ERRORS` on a
  fresh seed. Task 7 maps the new zone type onto this, not a new path.
- **`outdoor_dungeon` is a landscape zone type (task 7, 2026-11-02):**
  `zone_types.LANDSCAPE_ZONE_TYPES` (wilderness, outdoor_dungeon) is the one
  list of types that take `edges` and `trees` (CLI, server) and that the
  room-graph property samplers leave out. The planner checks its phrases
  (cave in a hill, hillside cave, barrow, ...) before the word scores. The
  sidecar's `outdoor_dungeon` block (envelope, rock cover, entrances with a
  tunnel id, outdoor spawn) comes from `outdoor_dungeon.sidecar_block`.
- **Maps need no outdoor-dungeon code (task 8, 2026-11-02):** M2's depth
  bands put the dungeon (with the lowland, the spawn's Main_Band) and the
  hill over it on separate bands, each with its own map file;
  `tests/test_outdoor_dungeon_maps.py` pins it on the shipped files.
- **The Tunnel opens into the entrance room (task 8, 2026-11-02):** an
  Envelope's optional `entry` (the approach foot) makes the room nearest it
  the layout's entrance, so pacing, elevation and keys run from the way in;
  `plan_entrance(room_id=)` digs only to that room. Never re-tag roles after
  the layout: room sizes, floors, themes and keys already follow them.
- **Plan at the largest room size that works (task 11, 2026-11-02):**
  `plan_dungeon` lays out and plans the Entrance at room scale 1, then
  0.85, 0.72, 0.61, and keeps the first plan with every room; theme and
  climax scaling outgrow the Envelope's sizing otherwise. Big races (ogre,
  giant) still never fit the default hill: their rooms are too tall.

## Follow-ups

Carried into `ROADMAP.md` by the close step (task 14).

- **Verticality (user, 2026-11-02, at the first look):** outdoor dungeons
  should go up and down, not only across. Today they are one level: the
  Envelope's height is the floor limit (150 u under the approach foot) to
  Rock_Cover (24 u) under a hill of about 110 u relief, with 80 u rooms;
  connectors are ramps only (grade 0.5, so height costs run); and the
  verticality control is ignored for this zone type. Cheapest first:
  (1) honour `verticality` here (deeper floor limit and larger rises on
  "dramatic"); (2) more relief: a taller hill or the `pit` Landform kind,
  entered by descending; (3) stacked levels joined by stairwells or shafts,
  which is ROADMAP step 7 ("Interesting dungeon verticality") and its
  "Multi-level / stacked-floor dungeons" item. The outdoor dungeon should be
  a first user of step 7. Its maps already give each level its own depth
  band (task 8).
- **Big-race outdoor dungeons (task 11, 2026-11-02):** an ogre or giant
  outdoor dungeon never plans (0/30 seeds, before and after task 11): the
  race scale makes rooms 112-176 u tall under a hill of about 110 u relief.
  Needs a host sized to the race (taller hill, or a pit), or race-capped
  room heights here. A design call for the user.
