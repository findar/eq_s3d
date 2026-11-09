# 18 — RoomContext and the room corpus

Index entry: `tasks.md` task 18. Requirements 13.1–13.3. Decision 15.

## Goal
`generators/room_context.py`: the RoomContext dataclass of the design's "Stages and the RoomContext" (floor grid and heights, ceiling heights, wall faces sampled from the built wall mesh, doors with Throats and clear zones, Spine, Features, POIs, type, kind, race, theme, zone type, Scales, seed), its versioned JSON form, `contexts(spec, mesh)` for every room of a built dungeon, city or outdoor dungeon, and `site_contexts(...)` for Sites (ground under the Site_Clear, Structures as Features, POIs). `scripts/record_rooms.py` records a corpus from pinned seeds covering every room type, wall style and race into `tests/fixtures/rooms/`. Nothing about any build changes.

## Done when
- [x] Contexts round-trip through JSON exactly; every room type, wall style and race is in the corpus; the corpus is small (a few MB at most).
      → verify: `python -m pytest tests/test_room_context.py -q -m "not slow"`
- [x] The `slow` contract test: a sample of the corpus re-recorded from its seeds equals the saved files.
      → verify: `python -m pytest tests/test_room_context.py -q -m slow`
- [x] Build bytes unchanged.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_room_layouts.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Wall faces come from the built mesh, not the outline: rough and hewn walls are noisy (design Risks). Keep the JSON stable (sorted keys, rounded floats) so re-recording diffs cleanly. Placement doesn't exist yet: don't design the context around a guess at it beyond the design's list; task 8 may add fields with a version bump.

## Result
✔ d08aa5c · 2116 passed
