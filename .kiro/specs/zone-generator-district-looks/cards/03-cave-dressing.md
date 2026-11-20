# 3 — Cave dressing

Index entry: `tasks.md` task 3. Requirement 3. Design "Task 3".

## Goal
- `cave` Purpose rooms are never lit `_WARM`; they take `_CAVE` at their Room_Type's intensity.
- The `cave` decor layer places no wall torches and no treasure dressing (chests, urns).

## Done when
- [ ] Over `cave` dungeons on both layouts with 8–30 rooms, no light is `_WARM`. Other Purposes'
      lights for `warren` and `collapsed_gallery` are unchanged.
      → verify: `python -m pytest tests/test_cave_purpose.py -q`
- [ ] 5 `cave` builds with Decor on place no torch and no chest or urn kinds. The commit body
      names the kinds checked. Same command (needs `EQ_PATH='F:\everquest_rof2'`).
- [ ] The byte check passes. If the cave recording `tests/fixtures/rooms/cave_graph.json` moves,
      it is re-recorded in its own commit with `scripts/record_rooms.py`.
- [ ] `python -m pytest tests/ -q -m "not slow"` is green.

## Pitfalls
- Keep the change to rooms of the `cave` Purpose (`room_theme == "cave"`). That includes a cave
  District in a districted zone.
- The decor rule format is in `docs/DECOR_RULES.md`.

## Result
