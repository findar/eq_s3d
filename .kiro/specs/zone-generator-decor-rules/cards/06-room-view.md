# 6 — The room view in the page

Index entry: `tasks.md` task 6. Requirement 5. Design "The room view" (Page); decisions 4, 5.

## Goal
`web/src/roomview.ts`: a Room view overlay that, while open, replaces the viewport with its own Three.js scene (Z-up, orbit camera framed on the room) showing the GLB `/api/room_decor` returns, POI markers, and labels on request; a list beside it grouping Props by recipe line (count and kinds), POIs with their Dressing, and drops with reasons, with two-way hover highlighting; a toolbar with ⟳ reroll (fresh decor seed), Decor level, Decor rules (layers), re-read rules (same seed, rules fresh) and Close. Open it from a room list in the side panel and by clicking a room in the map dialog. Closing returns to the zone with its camera and overlays as they were.

## Done when
- [ ] The frontend builds. → verify: `cd web; npx vite build`
- [ ] Opening a room of a build shows the same Props the zone has in that room (checked by comparing the route's report with the sidecar for one room of the Graph dungeon seed 2, 16 rooms; say how in the commit).
- [ ] `python -m pytest tests/ -q` is green; the Result says it was not checked in the browser by the agent (task 7 looks).

## Pitfalls
Movement keys stay suppressed while typing, and WASD must not move the zone's camera while the room view is open. Dispose the room scene's geometry and textures on close. Lessons-learned "Web viewer": the preview uses per-material base colours.

## Result
✔ e6db020 · 3178 passed · frontend builds · not checked in the browser by the agent beyond a scripted smoke run (task 7 looks)
