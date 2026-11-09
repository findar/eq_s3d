# 2 — Measure what fills stock rooms

Index entry: `tasks.md` task 2. Requirements 1.3, 1.4.

## Goal
`scripts/decor_survey.py`: put each placed object of finding 1's 15 dungeons and 15 cities in a room or corridor (step 9's chamber split) and report per zone and room style Props per room and per 1000 u² of floor, Category shares, Mount shares, lights' spacing along walls, Groups and what stands by doors. Write each catalogue entry's observed fields (height over the floor, distance to a wall, under a ceiling, scale, zone types) for every zone it's placed in. Measures importable, for task 14.

## Done when
- [ ] The script prints the per-zone tables; the catalogue's observed fields are filled.
      → verify: `python scripts/decor_survey.py --eq-path F:\everquest_rof2`
- [ ] Finding 1 has the final tables and bands for Props per room, Category shares and Mount shares, and says what the survey can't see.

## Pitfalls
Reuse step 9's chamber split (`scripts/room_feature_survey.py`). Outdoor zones get observed fields from the terrain under them, rooms or not.

## Result

