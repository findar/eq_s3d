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

From task 7 (decor recipes, `192400c`):

16. **Unmet recipe lines don't fail `check rules/decor`**; they're reported `unmet`, and fail
    only with `--strict` (run after the tag review). At build time an unmet line drops.
17. **A recipe line asks for a kind or alternatives, best first** (`["throne", "chair"]`); its
    Mount comes from `at` (`on_wall`/`wall` → wall, `ceiling`, `stack` → raised, else floor;
    a raised slot also takes a floor model).
18. **Weights by Layer are per-Category multipliers** blended by `room_scales.combine`
    (geometric mean); the Decor control multiplies on top; `bare` (0.26) is the chance a room
    takes only its Dressing; Clutter moves debris and Structure furniture (value/5). Task 8
    draws counts with `DecorRules.factor` / `draw_count`.
19. **Lookup is room type, else kind, else default, plus `[every]`**; a Site takes
    `[sites.<kind>]` only. **Sets:** race, then theme, then zone type, then neutral; two
    cultures share a room only where `[allows]` names the pair.

From task 8 (placement, `2bc13ad`):

20. **`place(context, rules, catalogue, control, decor_seed)` → `Decorated`** (props, drops,
    bare); `check(context, decorated)` is decor's own room check; `Prop.to_dict()` is the
    sidecar row. Each room's stream is keyed `decor/<seed>/<source>/<id>`.
21. **Yaw: a model's front is +X at yaw 0**; a wall Prop faces its wall's into-room normal
    (TORCHPOINT agrees over 177 stock placements; along-wall floor models are a guess).
22. **Dressing may stand in a Throat**, never on the Spine or a door's clear zone (else 24 of
    104 corpus POIs went undressed). Corridor contexts (`source = "corridor"`) get wall lights
    every 38 u (26 u in cities); task 9 must make them.
23. **Vertex-animated models stay out even when reviewed yes** (decision 13): 15 banners of
    review batch 1 were set back to `use = "no"` with a note.

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
