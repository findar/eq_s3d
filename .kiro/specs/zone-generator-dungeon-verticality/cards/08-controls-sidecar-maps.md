# 8 — Controls, sidecar and maps

Index entry: `tasks.md` task 8. Requirements 8. Design "Controls and sidecar".

## Goal
Verticality shows for graph dungeons and outdoor dungeons in the Controls panel; the sidecar's `layout` block records Levels, connectors and the Stacked_Share; a stacked build's maps put each Level on its own depth band.

## Done when
- [x] The Verticality select shows for dungeon (graph and classic) and outdoor dungeon (`CONTROL_ZONE_TYPES`); the frontend builds.
- [x] The sidecar has `levels`, `connectors` and `stacked_share`; a stacked build's EQ map files and outline split its Levels into depth bands (test on a built zone).
      → verify: `python -m pytest tests/test_level_sidecar_maps.py tests/test_hygiene.py -q`, `cd web; npx vite build`, then a generate through the browser pane (the lead checks it).
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- The frontend build stamps the git hash: build after the final commit, or the page shows a stale-build banner.

## Result
✔ edd683a · 1303 passed; browser check pending
