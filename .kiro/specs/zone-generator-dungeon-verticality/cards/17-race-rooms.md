# 17 — Rooms sized for their race

Index entry: `tasks.md` task 17. Requirements 10. Design "Race-sized rooms". Added at the user's request (2026-11-04).

## Goal
Replace the race multiplier with race bands: each race's body height H (finding 8) and the band multiples give a `[min, max]` room height and footprint; size classes pick inside the band (tiny at the minimum, huge at the maximum). Both engines use it; `dragon` joins the races (schema, Controls panel); the Level_Height follows.

## Done when
- [ ] V11: for every race and size class, in both engines, every room's height and footprint lie inside the race's bands; an ogre's smallest room is above a human's band minimum; a human's largest room is below a dragon's band minimum.
- [ ] `dragon` is a race in `ai/schema.py` and the Race select; a graph dragon dungeon builds and passes the gate.
- [ ] Builds without a race and classic unraced builds are unchanged (task 2 goldens of step 6); raced goldens that change are updated in this task's commit with old and new hashes and the reason.
      → verify: `python -m pytest tests/test_race_sizing.py tests/test_layout_engine.py tests/test_topology_embed.py -q`
- [ ] `python -m pytest tests/ -q` is green (the hygiene allowlists if a control changes), and the frontend builds.

## Pitfalls
- Step 6 task 20: the graph engine places rooms at their final race size and `semantics` must not scale them again; keep one place that sizes rooms.
- Step 6 decision: grown zones keep the classic floor area per room count. With bands, decide whether that still holds per race (a dragon dungeon is bigger) and say so in the commit body for `archive.md`.
- Big outdoor dungeons (step 5 follow-up): rooms taller than the hill. The Envelope may cap a race's maximum there; task 7 handles it.

## Result
