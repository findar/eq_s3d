# Archive — zone-generator-room-decor

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 17).

## Decisions

1. **Props are the client's own models, copied into the build** (user, 2026-11-08: "generating
   props will be hard to keep in line with existing eq look and feel. for a first pass we should
   use the pre-existing ones if possible which means we need to catalogue all of them as they
   exist and tag appropriately"). Every distinct model in the install's `_obj*.s3d` archives is
   catalogued and tagged; builds copy the ones they use, unchanged. Amends umbrella Req 32.7 for
   Props only.

2. **Its two consequences are accepted** (user, 2026-11-08: "i agree with those consequences"):
   builds with Props need the install (`EQ_PATH`), falling back to Decor `none` with a warning
   without it; and a built `.eqg` holds copies of the client's models and textures, for the
   user's own client and server, not to be shared as standalone files.

The design's other open questions (2-13) are answered here next.

## Follow-ups

Carried in from earlier steps and relevant here:

- **Reroll a room's contents while keeping its layout** (step 9): the decor seed (Req 9.2)
  covers Props; rerolling step 9's Structure and Clutter Features stays open.
- **Boulders read as short pillars** (step 9): left alone by open question 11's recommendation.
- **City room types** (tavern, home, shop): cities have none of their own (design question 8).
- **Generated Props** where the catalogue has nothing usable for a kind (design question 13).
- **Later-era `.eqg` models** (38,583 `.mod` names; design question 2).
- **Wilderness size** (step 10, the user's word to start).
- **Three dungeon and outline failures under the thorough profile** and the mapgeom
  face-order bug (step 10): proposed as one separate fix.
