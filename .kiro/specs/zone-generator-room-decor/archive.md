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
23. *(Superseded by 24.)* Vertex-animated models were first kept out even when reviewed yes:
    15 banners of review batch 1 were set back to `use = "no"`.
24. **Vertex-animated models are frozen in their rest pose and used** (user, 2026-11-10:
    "Freeze and use them", amending decision 13): the import takes the mesh's own vertices and
    ignores its animation track; such a model still enters builds only by review. Skeletal
    models stay out. The 15 banners are `use = "yes"` again.

25. **Proposed tags are accepted by default; the user corrects by feedback** (user, 2026-11-10:
    "instead of me reviewing all these, let's add them and then have support so i can remove as
    needed in the future or give feedback"), amending decisions 4 and 5 after four reviewed
    batches. Every `use = review` model enters builds; `tags.toml` lines (written by the user or
    by the lead from what the user says) remove or correct. The user also flagged doorway gates,
    parts used together, and ruined vs pristine versions. A probe of the 583 sheet models found
    only 5 door-like names, no name marking a ruined version, and few models sharing an origin
    (and those noisy), so: doors stay out by kind, `condition` is a new Tag set by feedback, and
    parts are `use = no` by feedback (task 19).

From task 19 (accept by default, `e3d4b8a`):

26. **`tags.toml` `accept = "proposed"`** lets every `use = review` model in: 3,247 usable
    (544 of the 583 dungeon/city sheet models); a `use` line always wins. Accepted models have
    `why["use"] = "accepted by default"`, `"use"` not in `reviewed`. Doors (kind `door`; more
    names go in `DOOR_NAMES`) are proposed `no`.
27. **`condition` is a Tag** (`pristine`, `ruined`, `unknown`); the first ruined or pristine
    Prop placed sets the room's, as the first culture sets its Set; all-unknown output is
    unchanged.

From task 9 (decor in builds, `9f75d97`–`acc21e3`):

28. **`ZoneSpec.decor` / `decor_seed`**, in the spec JSON only when set. `ZoneBuilder` treats
    an unset `decor` as none (golden bytes); the pipeline's `_with_decor` defaults it to
    normal. No install: no Props, warning `NO_INSTALL`, Decor-none bytes.
29. **ZON:** each model in use listed once after the Structures; objects `decor_NNNN`; lights
    `decor_light_NNNN` at the model's blended (flame) triangles, warm, radius 30, after the
    rooms' own lights. Floor, raised and ceiling Props are shifted so the model's plan lands
    on its footprint (`_at_origin`); wall Props keep stock's origin.
30. **Sidecar:** per room `props`, `dressing`, `decor_drops`; top-level `decor` = {control,
    seed, props, lights, models, rooms, bare, drops, check}. Texture manifest mode `decor`.
31. **Placement reads rooms as the gate does** (P13): walkable floor eroded by the player's
    half-width (plus 1 u at solid Features), Props about a step tall count, connectivity on
    both walkable and all reached floor, POI reach at the POI's level, and an 8 u clear way
    from each door to the room's middle. With that the gate's first try is 20/20 per zone type
    and the settle pass was removed. Build time +0.5 s (dungeon), w12 budget 9.1 of 10 s.

From task 10 (controls and maps, `bc541b4`–`999ee63`):

32. **Plan `decor: ""` means not chosen**; `plan_to_spec` sets `spec.decor`/`decor_seed` only
    when chosen (goldens unchanged). `VALID_DECOR` is written out in `ai/schema.py` (a test
    keeps it equal to `decor.rules.CONTROLS`). Prompt words: cluttered/furnished/lavish ->
    dense, bare/spartan -> sparse, unfurnished/empty rooms -> none.
33. **`GET /api/controls`** serves the page's lists (only `decor` so far). Reroll sends a
    top-level `decor_seed` with `seed` pinned; a reroll that fails the gate returns 503.
34. **Map Props come from the built `.eqg` plus the sidecar**, matched by position (0.05 u);
    floor Footprints as purple loops on the EQ map, dots for wall/raised/ceiling on the web
    map; drawn only over a traced outline.

From task 11 (Site Props, `1e3a6cb`):

35. **Every Site kind has a `[sites.<kind>]` recipe**; Sites go through the same `place()`.
    At Sites, Props stay inside the ground minus `SITE_MARGIN = 10`, keep `SITE_GAP = 6` from
    Structures and each other (closer walls off pockets), and Group members touch within
    `SITE_TOUCH = 2` or stand 6 u apart. Many stock models are open shells the wilderness gate
    rejects (533 refused); task 20 makes that screen catalogue data and wires Site Props into
    builds, which task 11 couldn't (`decor_for` skips roomless zones). The Decor control will
    cover wilderness.

From task 20 (Site Props in builds, `d2adbda`–`275f6ef`):

36. **The open-ground screen is catalogue data:** `"open_ground": true/false` on every
    non-skeletal floor or raised model (2,414 kept, 1,616 refused), written by
    `prop_catalogue.py screen` (~40 min, one-off); only `true` models go at Sites. A Mount
    changed in `tags.toml` needs a rescreen (a test flags it).
37. **`decor_for` places rooms, then Sites** (`rooms=False` for the wilderness gate ZON). Site
    Props ride on each Site's sidecar row (`props`, `dressing`, `decor_drops`, `bare`), never
    on `rooms`; the maps draw them too. Decor covers wilderness. About 4 Props per Site at
    Normal, 6 at Dense; a wilderness build takes up to 0.6 s longer.

From task 13 (first-look fixes, `9ba2890`–`0ac6dfe`; user's first look 2026-11-10: "mostly ok
for a first pass", banners invisible, torches not mounting on the wall, a box below the world):

38. **`wall_side` in the catalogue:** each wall model's side to the wall, distance off it and back
    depth, measured from stock placements (277 models, 254 measured). A wall Prop turns that side
    to the wall; the build moves it to 0.05 u off the real wall mesh at its height, or drops it
    ("no wall") when that move exceeds 1 u (4 of 222 at corners and notches). Amends decision 21.
39. **Floor Props stand on their bottom**, 0.05 u over the lowest floor under their plan; a
    stacked Prop sits on the top of the one below. Amends decision 29's `_at_origin`.
40. **The Site screen judges each model standing on its bottom** (rescreen: 2,379 kept, 1,651
    refused); at Sites a Prop's top stays at least 0.25 u (`SITE_STEP_SLACK`) off the step height.
41. **The viewer's decor colour averages drawn texels only** and never-drawn faces are skipped,
    so mostly-transparent banners show.

## Follow-ups

- **From task 13:** the scale limit makes GENMETCRATE700 twice its stock size; floor models
  placed along a wall still assume their front is +X; the `.eqg` rotation direction is unchecked
  in the client; wall Props at corners aren't checked for poking sideways into the wall.

- **`web/index.html` tooltips** still say Decor is "in the rooms"; Sites take it too.

- **Corridor lights:** placement lights `source = "corridor"` contexts, but `room_context`
  builds none yet (task 13 or later).

- **Doorway gates as doors** at room openings (with the EQEmu `doors` records, M6).
- **Assemblies placed whole**: pieces stock always places together, as Groups copying stock's offsets.

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
