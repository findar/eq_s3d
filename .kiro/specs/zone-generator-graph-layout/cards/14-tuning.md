# 14 — Tune from the first look

Index entry: `tasks.md` task 14.

## Goal
Answer the first look's findings (task 13's card). The one tuned here: a themed or big-race graph dungeon must be possible from the Controls panel alone. Today the panel has no dungeon theme or race, so those builds need the description box, which ignores the Layout toggle. Add **Theme** and **Race** selects to the Controls panel, sent as controls the server turns into `ZonePlan.dungeon_theme` / `dungeon_race`, for the zone types that use them. The other finding (rooms look alike) is a follow-up for steps 8 and 9, already in `archive.md`.

## Done when
- [x] The server's controls take `dungeon_theme` and `dungeon_race` (values from `ai/schema.py`'s `VALID_DUNGEON_THEMES` / `VALID_DUNGEON_RACES`, "" for none); a bad value is a 400 naming the allowed values; zone types that don't use them reject or ignore them by the same convention as the other type-specific controls.
- [x] The Controls panel has Theme and Race selects ("None" first), shown through the `CONTROL_ZONE_TYPES` table for the zone types that take them, sent with the controls; a graph temple dungeon and a graph ogre dungeon build from the panel alone and their sidecars show the theme, race and layout.
      → verify: `python -m pytest tests/test_server.py tests/test_hygiene.py tests/test_graph_layout_controls.py -q`, `cd web; npx vite build`, then a generate through the browser pane (the lead checks it).
- [x] `python -m pytest tests/ -q` is green (the web-control allowlist in `tests/test_hygiene.py` gains the two ids).

## Pitfalls
- Frontend-only changes never run the Python suite: task 11 broke two hygiene tests that way. Run it.
- The theme and race lists in the page: take them from the server if it already exposes them (e.g. a zone-types or info route); if not, hard-code them and say so, as task 11 did for rule sets.

## Result
✔ d7a55c0 · 1219 passed; browser check ✔ (graph temple and graph ogre from the controls alone); temple nave fixed from 7 rooms
