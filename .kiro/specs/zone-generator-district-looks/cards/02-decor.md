# 2 — Decor per District

Index entry: `tasks.md` task 2. Requirement 2. Design "Task 2".

## Goal
In a multi-District dungeon, each room's Decor uses its District Purpose's decor layers, and each
corridor uses the layers of its `from_room`. A partial rebuild equals a full build.

## Done when
- [ ] A districted dungeon with a `cave` District after a `fortress` District, Decor on:
      - the cave District's rooms take models only from the cave layer and the shared base (no
        benches or banners);
      - the fortress District's rooms keep the fortress layer.

      → verify: `python -m pytest tests/test_district_decor.py -q` (needs
      `EQ_PATH='F:\everquest_rof2'`)
- [ ] The sidecar's decor record names each District's layers, and a one-District build's record
      is unchanged. Same command.
- [ ] A districted partial rebuild, with one room's decor reseeded, equals a full build.
      → verify: `python -m pytest tests/test_partial_rebuild.py -q`
- [ ] The byte check passes, and `python -m pytest tests/ -q -m "not slow"` is green.

## Pitfalls
- `_decor_data` is cached, so load the rules once per Purpose, not once per room.
- `BareCap` counts bare rooms against one rule set today. Check that it still holds per District.
- `generators/builder.py` is large; edit only the decor functions.

## Result
