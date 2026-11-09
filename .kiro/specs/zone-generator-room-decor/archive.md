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

The design's other open questions, answered by the user 2026-11-08 ("Take them all" to every
recommendation, master `510a406`). Decision N answers design question N - 1:

3. **Archives: the 293 `_obj*.s3d` (4,408 models)**, the Classic–PoP look; `.eqg` models later.
4. **Review covers what recipes draw on**: the models stock places in dungeons and cities (581
   names). The rest stay `use = review`, out of builds. Review can stop part-way.
5. **The user reviews**, on the contact sheet, correcting `rules/decor/tags.toml` or telling the
   lead to write it (task 4, human).
6. **Collision is stock's flags**, unchanged; a model that blocks wrongly is `use = no`, not edited.
7. **Wall and ceiling Mounts are in v1.**
8. **Each light-bearing Prop adds a ZON point light**; the room's centre light stays.
9. **Cities are in v1**, with a city Layer toward furniture and lights; city room types later.
10. **Site Props are in v1** (task 11), static models only.
11. **Both a Decor control and a decor seed**, with a "Reroll decor" button on a built zone.
12. **Step 9's mesh Boulders stay**; stock rocks add debris on top.
13. **Static models only**; animated ones are recorded in the catalogue for later.
14. **No generated Props in this step**; a recipe line with no usable model drops.

Added after the answers:

15. **Decor stands on its own** (user, 2026-11-08, "soounds good lets do that", to the proposal
    of stages with saved hand-offs): the room stage writes one RoomContext per room and Site;
    placement reads only that; decor tests run on a recorded room corpus without zone builds,
    with one contract test keeping the corpus honest (Req 13, task 18). The world -> Socket
    stage is roadmap step 12, its own spec.

## Follow-ups

Carried in from earlier steps and relevant here:

- **Reroll a room's contents while keeping its layout** (step 9): the decor seed (Req 10.2)
  covers Props; rerolling step 9's Structure and Clutter Features stays open.
- **Boulders read as short pillars** (step 9): left alone by open question 11's recommendation.
- **City room types** (tavern, home, shop): cities have none of their own (design question 8).
- **Generated Props** where the catalogue has nothing usable for a kind (design question 13).
- **Later-era `.eqg` models** (38,583 `.mod` names; design question 2).
- **Wilderness size** (step 10, the user's word to start).
- **Three dungeon and outline failures under the thorough profile** and the mapgeom
  face-order bug (step 10): proposed as one separate fix.
