# 9 — Reroll rooms on the page; Sockets on the map

Index entry: `tasks.md` task 9. Requirement 4.3.

## Goal
On a built zone, a "Reroll rooms" button beside "Reroll decor": it sends the zone's seed and a fresh `rooms_seed`. The side panel shows the build's `seeds` block. The web map marks each Socket from the sidecar's `sockets` block (a hillside's approach point and side, the ground's Spawn), with a tooltip naming its kind and what attached.

## Done when
- [ ] The frontend builds.
      → verify: `cd web; npx vite build`
- [ ] `python -m pytest tests/ -q` is green (the hygiene guard on control ids included).
- [ ] The Result says it was not checked in the browser by the agent; task 15 looks.

## Pitfalls
Movement keys must stay suppressed while typing in a field (lessons-learned "Web viewer"). A commit-message hook blocks two words about the frontend build (lessons-learned "Environment"). `web/node_modules` is shared through a junction: don't change dependencies.

## Result
