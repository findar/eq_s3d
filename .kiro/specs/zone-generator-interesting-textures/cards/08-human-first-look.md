# 8 — HUMAN: first look at the new textures in 3D

Index entry: `tasks.md` task 8. **Type: human. Agents never tick this.**

## Setup
Merge tasks 1–7, restart the server, and generate a themed dungeon ("a gnoll
temple dungeon"), a lava-tinted dungeon ("a kobold tomb full of lava"), an
ice keep ("a giant ice keep"), a plain dungeon and a city.

## Checklist
- [x] Surfaces read as their material: blocks or bricks on walls, slabs or
      cobbles on floors, rock on cave ceilings, sky over city streets.
- [x] The look reads as Classic–PoP EverQuest: dark, saturated, crisp.
- [x] The scale feels right (a stone block about a player's height or less).
- [x] Repetition and seams aren't distracting.

## Result
Signed off by the user (2026-11-01) with one finding for task 9:
- "when i did 'a gnoll temple dungeon' the hall way floors did not match the
  room floors. i would expect hallways to match an adjacent room." Corridors
  used the shared `<race>_dungeon_*` materials while themed rooms used
  `<race>_<theme>_*`.
