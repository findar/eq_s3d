# Archive — zone-generator-world-sockets

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

The user's answers to the design's open questions go here, numbered as the questions are.

## Follow-ups

Carried in from step 11 (`zone-generator-room-decor/archive.md` "Follow-ups") because they
sit on the stage hand-offs this step builds:

- **Corridor lights**: placement lights `source = "corridor"` contexts, but `room_context`
  builds none. Task 14, if design question 7 is answered yes; otherwise it stays here.
- **Reroll a room's contents while keeping its layout** (step 9): the decor seed covers
  Props, and this step's `rooms_seed` rerolls the whole layout; a seed for step 9's Structure
  and Clutter Features alone (the Attach stage split into layout and contents) stays open.
- **Doorway gates as doors** at room openings (M6, with the EQEmu `doors` records): related to
  the reserved `door` Socket kind (design question 3), not built here.

Carried in from step 10 (`zone-generator-wilderness-pois/archive.md` "Follow-ups"), because
point Site Sockets (design question 2) are where they would be fixed:

- **Sites spread at random** where stock plains cluster them.
- **Outdoor dungeons get Sites on only some seeds**: their open ground is small (about
  0.8e6 u²).

Out of this step, named so they aren't lost:

- An exact Mouth Socket chosen by the World, and more than one dungeon in a World (design
  question 1).
- Rerolling only the stage a gate failure names (design question 5); M4's partial rebuild.
- Multi-zone worlds and zone lines between zones; the M6 SQL export.
