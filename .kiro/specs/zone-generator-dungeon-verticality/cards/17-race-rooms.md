# 17 — Rooms sized for their race, at stock scale

Index entry: `tasks.md` task 17. Requirements 10. Design "Race-sized rooms", finding 8. Added at the user's request (2026-11-04); the user chose stock scale.

## Goal
Every dungeon's rooms and corridors are sized from the resident race's body height H (finding 8: `racedata.txt`; the default race is a human, H = 6 u) at the stock bands: room height 2.5-10 H, footprint side 8-20 H. Size classes pick inside the band (tiny at the minimum, huge at the maximum). This replaces the race multiplier (`semantics.RACE_SCALE`) AND today's zone-type base size (`_apply_room_scale`'s measured whole-zone floor area divided by the room count, which made human rooms 121 u tall and ~340 u across). Both engines; `dragon` joins the races (schema, the Race select). Corridor widths follow stock (step 6 survey: stock corridors 12-28 u, about 2-5 H). The Level_Height (Req 4) follows from the banded heights.

## Done when
- [ ] V11: for every race and size class, in both engines, every room's height and footprint lie inside the race's bands; corridor width and height inside a corridor band from H; an ogre's smallest room is above a human's band minimum; a human's largest room is below a dragon's band minimum.
- [ ] `dragon` is a race in `ai/schema.py` and the Race select; a graph dragon dungeon builds and passes the gate.
- [ ] Every build changes size (this is the decision): the goldens are recaptured in this task's commit, old and new hashes listed with the reason; the walk gate passes on the step 5 and step 6 build tests and the gate sweeps at the new scale, first-try rates no worse than before (both in the commit body); step 6's shape bands and fidelity bars still hold.
- [ ] The earlier acceptance sections' cases (`docs/ACCEPTANCE.md` M1 through step 6) still build first try at the new scale; where a pinned seed no longer does, pick another and note it.
      → verify: `python -m pytest tests/test_race_sizing.py tests/test_layout_engine.py tests/test_topology_embed.py tests/test_graph_layout_build.py tests/test_outdoor_dungeon_build.py -q`
- [ ] `python -m pytest tests/ -q` is green (the hygiene allowlists if a control changes); the frontend builds.

## Pitfalls
- One place sizes rooms (step 6 task 20: the graph engine places rooms at their final size, and `semantics` must not scale them again). Keep it that way for both engines.
- Constants tuned at the old scale: corridor clearance in `_separate_rooms`, ramp runs (`max_grade` × run: smaller rooms mean shorter runs and gentler rises), the Envelope fit and `outdoor_dungeon.ROOM_HEIGHT` (80 u), the Tunnel's minimum wall (step 6 task 10), the 60 s and timing budgets. Re-check each; fix root causes, not tests.
- Step 6 decision "grown zones keep the classic floor area" now holds per race through the bands; say in the commit body how the zone's total size follows.
- The walk agent's player height is 6 u and the human H is 6 u: rooms 15 u tall still clear it, but corridors and doorways must too (headroom ≥ player height).
- Big outdoor dungeons (step 5 follow-up): rooms taller than the hill; at stock scale they may now fit; measure it (task 7 owns the rest).

## Result
