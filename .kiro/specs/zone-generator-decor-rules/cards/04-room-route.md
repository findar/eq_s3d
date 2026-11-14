# 4 — Re-decorate one room: module and route

Index entry: `tasks.md` task 4. Requirement 4. Design "The room view"; decision 4.

## Goal
`generators/decor/room_view.py`: `decorate_room(contexts, room_id, *, seed, control, layers, eq_path)` returns a GLB of the room alone (what `scripts/decor_room.py` draws today) and a report (`props` with `line`, `step`, `at`, `key`, `kind`, `category`, position; `pois` with purpose, position and Dressing; `drops` with line, what and reason; `seed`, `control`, `layers`, `took_ms`). It decorates exactly as the build does (the same placement entry and seed derivation), so the build's own seed gives the build's Props. `scripts/decor_room.py` becomes a thin CLI on it. `POST /api/room_decor` `{zone, version, room, decor_seed?, control?, decor_layers?}` reads the build's `<name>.rooms.json`, reads the rule files fresh, writes the GLB under the build folder and answers the report with a `glb_url` served by the build-file route; a failing rule check → 400 with the errors; paths through `core/paths` and `_safe_segment`.

## Done when
- [ ] For the decor goldens' builds, the route's Props for every room equal the sidecar's `rooms[].props`; a fresh decor seed changes them; an edited rule file (a temporary rules folder) shows without a restart; a bad rule file gives a 400; a bad zone or room id gives a 400/404, never a path outside the output root. → verify: `python -m pytest tests/test_room_view.py -q`
- [ ] Time: under 3 s for a room of the 16-room Graph dungeon seed 2, models cached (measure; numbers in the commit body).
- [ ] `python scripts/decor_room.py tests/fixtures/rooms/war_city_troll.json --out output/decor_room` still writes its GLB.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Lessons-learned: `fullmatch` for path segments; `Path.resolve` and the `\\?\` prefix (go through `core/paths`). The build cache (`_decor_data`) must not be what the route reads: rules are fresh per call. The install (`EQ_PATH`) may be missing: answer with boxes, as `decor_room.py --boxes` does, and say so in the report.

## Result
