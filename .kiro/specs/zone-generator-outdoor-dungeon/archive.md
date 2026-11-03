# Archive — zone-generator-outdoor-dungeon

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Signed off 2026-11-03; master `1ad814f`. Suite 1019 (fast; thorough green).

| Task | What landed |
|------|-------------|
| 1 | Walk-based anatomy survey of classic outdoor dungeons (`scripts/outdoor_dungeon_survey.py`): rock cover p10 12-22 u, covered floor at most ~130 u under the open ground |
| 2 | `generators/envelope.py`: the 3D Envelope (footprint, floor limit, surface, Rock_Cover) and room layout inside it, dropping rooms with a `rooms_reduced` warning |
| 3 | `Landform` on the Design_Matrix (`hill` or `pit`, backed onto a mountain side); the default Host_Hill at the 1200 u outdoor-dungeon size |
| 4 | Envelope from the built TER (`host_envelope`); 80 u rooms sized to it; `_fit_floors` shifts by the tightest room |
| 5 | The Entrance on the terrain grid: Apron trench, one-cell Tunnel, Mouth stitched to the terrain's own vertices; one merged TER |
| 6 | `outdoor_dungeon_spec` (a wilderness spec carrying the dungeon), `TerrainBackend` builds it, `outdoor_dungeon_report` gates it (bowl + every room from the outdoor spawn), plan errors retried |
| 7 | `outdoor_dungeon` zone type: prompt phrases, CLI, server, `LANDSCAPE_ZONE_TYPES` for edges and trees, sidecar `outdoor_dungeon` block |
| 8 | Maps need no new code (dungeon and hill on separate depth bands, pinned by tests); fix: the Tunnel opens into the layout's entrance room (Envelope `entry`) |
| 9 | Web: the zone type offered with the controls each type uses (one table in `main.ts`) |
| 10 | First look signed off; one finding (verticality) recorded as a step 7 follow-up |
| 11 | `plan_dungeon` shrinks rooms until a themed dungeon plans (fortress failures 15/30 -> 2/30) |
| 12 | ACCEPTANCE "Step 5 — Outdoor dungeon"; 60 s budget test (6.8 s); thorough run green |
| 13 | Human acceptance pass: signed off, no findings |

Not done here, carried forward: more than one level (ROADMAP step 7, see
Follow-ups), staircase and bridge connectors (ramps only, step 7), and ogre
or giant outdoor dungeons (rooms taller than the hill).

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
