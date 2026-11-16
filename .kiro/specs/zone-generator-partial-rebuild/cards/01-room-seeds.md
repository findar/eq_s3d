# 1 — Room decor seeds

Index entry: `tasks.md` task 1. Requirement 3. Design "Room decor seeds"; decision 4.

## Goal
`ZoneSpec.room_decor_seeds: Dict[str, int]` (left out of `to_dict` when empty, read back by
`from_dict`) and `ZonePlan.room_decor_seeds` (validated: known shape, seeds in the seed range),
carried by `plan_to_spec`. `decor_for` places a room that has its own seed with that seed, in the
same placement entry, while every room's bare decision is still drawn from the zone's decor seed
(the `BareCap` order). The sidecar's `seeds` block lists `room_decor_seeds` when non-empty and
each such room's record names its `decor_seed`. `room_view.decorate_room` reports the decor seed
it used, and "As built" takes the room's own.

## Done when
- [ ] With no room decor seeds every build is byte-identical. → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_site_decor_builds.py -q`
- [ ] A room decor seed changes that room's Props and no other room's (Props, bare flags), on the 16-room Graph dungeon seed 2 and a city; the room view's "As built" for that room equals the build's Props; `ZoneSpec` round-trips it. → verify: `python -m pytest tests/test_room_decor_seeds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
A room whose own seed would make it bare under the zone's draw: the bare decision is the zone's,
so it stays as the zone drew it; say so in a docstring. The room view replays bare decisions
already (`bare_replayed`): keep one rule for both. Don't touch `server/app.py` (task 2 owns it);
the request field arrives in task 3.

## Result
✔ d847e28 · 3192 passed
