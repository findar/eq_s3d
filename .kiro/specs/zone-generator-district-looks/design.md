# Design: zone-generator-district-looks (roadmap step 22)

Written at master `b11764b`. Verify everything here against the code before working.

## Where each look is chosen today

| Look | Where | Today | Task |
|---|---|---|---|
| Scales (Finish → wall style) | `generators/room_scales.py` `draw_room_scales`, line ~128 | `rules.layers_for(spec.dungeon_race, spec.dungeon_theme, ...)` | 1 |
| Decor layers | `generators/builder.py` `decor_layers_of`, `_decor_data(...)` once per build (~line 791) | zone's `dungeon_theme` | 2 |
| Decor weights (per room) | `generators/room_context.py` ~528 | already `room.room_theme or spec.dungeon_theme` | — |
| Corridor context | `generators/room_context.py` ~700 | `spec.dungeon_theme` | 2 |
| Room light | `generators/semantics.py` `ROOM_TYPES[...].light`, `_set_room_light` | the Room_Type's colour, whatever the Purpose | 3 |
| Cave decor | `rules/decor/layers/cave.toml` | no weight against torches or treasure | 3 |
| Cave room height | `generators/layout.py` `_apply_room_scale` and the profile Size shift (step 21 task 4, `ai/expand.py` `PURPOSE_PROFILE`) | the shift lowers heights too | 4 |

`room_theme` is set when rooms are labelled (`semantics.py` ~551, and ~1019 for Districts). That
runs before `ai/expand.py` `_dress_rooms` calls `draw_room_scales`, so task 1 can read it.

## Task 1: walls per District

Use `room.room_theme or spec.dungeon_theme` as the theme argument of `layers_for`. One-District
zones are unchanged because their `room_theme` equals `dungeon_theme`. Prove that with the byte
check, not by reasoning. Rooms lean toward their neighbours' Scales only within a wing, so a
District edge can still blend. Leave the lean alone and record what the walls look like across a
Threshold in the commit body.

## Task 2: decor per District

Load `_decor_data(layers)` once per distinct Purpose in the zone. `_decor_data` is cached, so a
lookup costs nothing. Pick each context's rules by its room's (or its corridor's `from_room`'s)
`room_theme`. `BareCap` and `DecorBuild.layers` take the zone's rules today. Keep `DecorBuild`
recording what it does now for a one-District zone, and add the per-District layers under a new
key only when there are Districts. Partial rebuild (`generators/rebuild.py`, `SavedStages`) must
reach the same result as a full build. `tests/test_partial_rebuild.py` covers this, so add a
districted case to it.

## Task 3: cave dressing

- **Light:** in `label_rooms` / `_apply_regions_and_lights`, a room whose `room_theme` is `cave`
  and whose Room_Type's light is `_WARM` takes `_CAVE` at the Room_Type's intensity. Keep it to
  rooms of the `cave` Purpose; no other Purpose's bytes move.
- **Decor:** zero weights in `rules/decor/layers/cave.toml` for the Categories or kinds that place
  wall torches and treasure. Check against the format in `docs/DECOR_RULES.md` which form the
  rules accept (a Category weight, or a kind weight).

## Task 4: cave ceilings

Find where the profile's Size shift reaches room height (`_apply_room_scale`,
`semantics.room_height`). Apply the shift to footprint only, for the profile path only.

## Gate and bands (task 5)

`scripts/sweep_themed_navigability.py` runs districted dungeons for both layouts and 8–30 rooms,
with District Purposes pinned so that each run has a cave District and a built one in both orders.
`scripts/quality_sweep.py` measures the fail share of districted Draws against today's bands.
