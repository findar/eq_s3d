# 4 — The plan and the prompt

Index entry: `tasks.md` task 4. Requirements 4.1, 4.2. Design "Plan, prompt and Server".

## Goal
`ZonePlan.districts`, `district_plan`, `district_relationship` (validated, saved, loaded with
defaults); `plan_to_spec` passing them to the layout for dungeons (a note otherwise, A2); the rule
planner's contrasting-area phrases (23.9); the LLM planner's schema and prompt carrying the same
fields.

## Done when
- [x] A plan round-trips the three fields; a saved plan without them loads off; unknown Purposes
      or relationship are kept out by validation with a note (23.12). → verify:
      `python -m pytest tests/test_district_plan.py -q`
- [x] "a temple fallen to the dead", "two factions of goblins", "the upper and lower mines" turn
      Districts on with the count, Purposes and relationship the phrase names; a prompt with no
      phrase leaves them off. Same command.
- [x] `python -m pytest tests/ -q` is green (including the property tests on plans and planner
      words).

## Pitfalls
Planner word tests are touchy (step 19's thorough run failed `test_cave_words_mean_dungeon`
outside its scope); don't let a District phrase move the zone type or Purpose matching. A
District field on a wilderness or city plan is kept but ignored by `plan_to_spec` with a note.

## Result
✔ ff0021a · 3703 passed
