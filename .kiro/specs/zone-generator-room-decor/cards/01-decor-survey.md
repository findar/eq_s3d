# 1 — Measure what fills stock rooms

Index entry: `tasks.md` task 1. Requirements 1.

## Goal
`scripts/decor_survey.py`, from the design's finding 1: put each placed object of the 15 dungeons and 15 cities in a room or corridor (step 9's chamber split), and report per zone and room style Props per room and per 1000 u² of floor, Category shares, Mount shares (height over the floor, distance to a wall), lights' spacing along walls, Groups (chairs by tables, bed rows), and what stands by doors. Measure the common stock Prop models from `<zone>_obj.s3d`: triangles, plan, height, collidable share, texel density. Measures importable, for task 12.

## Done when
- [ ] The script prints the per-zone and per-model tables.
      → verify: `python scripts/decor_survey.py --eq-path F:\everquest_rof2`
- [ ] Finding 1 has the final tables and bands for Props per room, Category shares and Mount shares, and says what the survey can't see.

## Pitfalls
Reuse `room_feature_survey.placed_objects` and the chamber split; `site_survey.measure_model` measures a model. Name patterns are rough: check the leftovers by hand. No tests, apart from what task 12 imports.

## Result

