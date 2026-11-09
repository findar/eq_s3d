# 8 — Decor placement in rooms

Index entry: `tasks.md` task 8. Requirements 5, 6, 8, 13.4, 13.5.

## Goal
`place(context, ...)` reads one RoomContext (task 18) and nothing else. Per room, on its own salted stream: Dressing at each POI, then Groups, then single Props, then debris by Clutter, each a `use = yes` model with the asked Tags from the room's Sets. Floor spots off the Spine, Throats and Features; along-wall models backed to the wall; wall spots at stock's observed height, clear of doors; ceiling spots under enough headroom; Groups whole or dropped; corridors get wall lights by spacing. Drops recorded. Decor checks its own result against the context (reached floor joined, doors and POIs reached). `scripts/decor_room.py <context.json>` writes a GLB of one decorated room.

## Done when
- [ ] P5 and P8 over the whole room corpus and hand-built contexts, no zone builds; one culture per room.
      → verify: `python -m pytest tests/test_decor_placement.py -q -m "not slow"`
- [ ] P13: placement imports nothing from the room stage but `generators/room_context.py`.
      → verify: `python -m pytest tests/test_decor_placement.py -q -k imports`
- [ ] One corpus room decorates to a GLB in under 5 s.
      → verify: `python scripts/decor_room.py tests/fixtures/rooms/<any>.json --out output/decor_room`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Wall spots on rough walls must sample the wall mesh, not the outline (design Risks). Step 10 decision 10 sets yaw.

## Result

