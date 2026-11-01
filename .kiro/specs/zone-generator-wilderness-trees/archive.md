# Archive — zone-generator-wilderness-trees

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 14).

## Decisions

The design's "Decisions" section (1–5) stands. The user answered its open
questions on 2026-10-31, each with the recommended option:

- **Tree collision (Open question 1):** trunk solid, canopy walk-through, as in
  the classic Karanas. Trunks keep Tree_Clearance so a player always passes.
- **Density control (Open question 2):** prompt words plus a Trees selector
  (none / sparse / normal / dense) on the web and CLI.
- **Rim slopes (Open question 3):** no trees on the rim; plains below 30° only.
- **Maps (Open question 4):** no trees on the EQ `.txt` or the web SVG.
