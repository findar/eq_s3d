# 5 — Planner words, page and Districts

Index entry: `tasks.md` task 5. Requirement 4. Design "Planner, page and Districts".

## Goal
Cave words choose Purpose `cave` in the rule planner (A5); "Cave" in the page's Theme list;
`cave` in Districts' compatibility pairs.

## Done when
- [ ] "a dark cavern", "a crystal grotto deep underground", "winding tunnels" plan as dungeon +
      `cave`; "an old mine" stays `mine_delve`; "a flooded temple in a cave" keeps `temple` if it
      scores higher (state the rule in the commit body); zone types unchanged. → verify:
      `python -m pytest tests/test_planner.py tests/test_properties_layout.py -q`
- [ ] `sequential` and `factional` Districts can draw `cave` with the neighbours of design
      "Planner, page and Districts"; a pinned `cave` gives every District `cave`. → verify:
      `python -m pytest tests/test_district_purposes.py -q`
- [ ] `cd web; npx vite build` succeeds; `python -m pytest tests/ -q` is green.

## Pitfalls
Planner word tests are touchy (step 19's thorough failure `test_cave_words_mean_dungeon`); keep
the zone-type buckets as they are. Property 19's assertion stays; only its wording changes.
Never write the frontend tool's name or "dev server" in a commit message.

## Result
