# 7 — The outdoor dungeon keeps its dungeon clear

Index entry: `tasks.md` task 7. Requirements 5, 7.2. Design "The outdoor dungeon", finding 3, questions 3 and 4.

## Goal
`stages.entrance_keep_clear` returns the dungeon's rooms and corridors (capsules grown by `SITE_CLEAR` + 8 u), the Tunnel and the Apron, and no hill disc. `site_target` gives an outdoor dungeon at least one Site at Normal and Dense. Delete `outdoor_dungeon.keep_clear_shapes` (step 12 follow-up) and move its test callers to `entrance_keep_clear`. Outdoor-dungeon builds with Sites change again: recapture their goldens and `outdoor_*` Site recordings in this task's commit, Site counts before and after in its body.

## Done when
- [ ] P7: over the World corpus's outdoor dungeons and seeds 0–39, no Site, Structure or Site_Clear over a room, corridor, Tunnel or Apron.
      → verify: `python -m pytest tests/test_attach_ground.py -q`
- [ ] P8, placement only: at Normal, a Site on at least 35 of the planning seeds 0–39 (today 8), the count in the commit body. If short, the World's spares are what to raise: stop and say so (task 3's file).
      → verify: `python -m pytest tests/test_attach_ground.py -q -k outdoor`
- [ ] Wilderness, dungeon, city and Sites `none` bytes unchanged; outdoor-dungeon goldens recaptured.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_world_corpus.py -q` and `python scripts/record_rooms.py --check`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
A room's capsule must cover its corners: half the short side times √2, as finding 3 measured. Stacked Levels put rooms over each other: take every room. Kept_Clear never moves the Spawn. Trees keep step 5's ground; don't change what they read.

## Result
