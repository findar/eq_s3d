# 8 — Decor placement in rooms

Index entry: `tasks.md` task 8. Requirements 5, 6, 8.

## Goal
Per room, on its own salted stream: Dressing at each POI, then Groups, then single Props, then debris by Clutter, each a `use = yes` model with the asked Tags from the room's Sets. Floor spots off the Spine, Throats and Features; along-wall models backed to the wall; wall spots at stock's observed height, clear of doors; ceiling spots under enough headroom; Groups whole or dropped; corridors get wall lights by spacing. Drops recorded.

## Done when
- [ ] P5 and P8 over many seeds and every room type; one culture per room.
      → verify: `python -m pytest tests/test_decor_placement.py -q`
- [ ] The plan grid is unchanged for every room (step 9's goldens).
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_room_layouts.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Wall spots on rough walls must sample the wall mesh, not the outline (design Risks). Step 10 decision 10 sets yaw.

## Result

