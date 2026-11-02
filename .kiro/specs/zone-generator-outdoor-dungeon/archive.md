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
