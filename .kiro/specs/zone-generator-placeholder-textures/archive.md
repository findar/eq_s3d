# Archive — zone-generator-placeholder-textures

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 10).

## Decisions

The design's "Decisions" section (1–4) stands. The user answered its open
questions on 2026-11-01, each with the recommended option:

- **Placeholder look (Open question 1):** base colour, a Surface_Class
  pattern and the Material_Name as text.
- **Default Texture_Mode (Open question 2):** `placeholder` for every build;
  `procedural` and `ai` stay selectable with `EQ_S3D_TEXTURE_PROVIDER`.
- **Textured preview (Open question 3):** in step 3 (Req 6); trees stay in
  base colours.
- **Race in the set name (Open question 4):** race first
  (`gnoll_temple_wall`, `gnoll_dungeon_floor`).
