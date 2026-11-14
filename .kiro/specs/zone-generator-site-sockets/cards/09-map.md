# 9 — Point Sockets on the map

Index entry: `tasks.md` task 9. Requirement 9. Design "Hand-offs", question 7.

## Goal
`generators/mapview.py` writes its world-to-pixel frame on the map SVG (`data-` attributes holding `a`, `b` and `s` of `u = a + s·x`, `v = b − s·y`). `web/src/sockets.ts` reads the frame from them (the room-label fit stays only as a fallback for maps made before) and draws each `site` Socket as a small diamond: filled when a Site attached, hollow when unused, a tooltip naming its Group and the Site's kind. `web/src/api.ts` types the new sidecar fields.

## Done when
- [ ] The map SVG carries the frame, and the frame maps each room's centre to its label.
      → verify: `python -m pytest tests/test_properties_mapview.py -q`
- [ ] The frontend builds.
      → verify: `cd web; npx vite build`
- [ ] `python -m pytest tests/ -q` is green; the Result says it was not checked in the browser by the agent (task 12 looks).

## Pitfalls
`tests/reference_mapview.py` and the mapview property tests compare SVG output: add attributes without changing anything drawn. Movement keys stay suppressed while typing (lessons-learned "Web viewer"). A commit-message hook blocks two words about the frontend build (lessons-learned "Environment"). `web/node_modules` is shared through a junction: don't change dependencies.

## Result
