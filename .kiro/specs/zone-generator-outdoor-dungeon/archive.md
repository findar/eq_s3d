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
