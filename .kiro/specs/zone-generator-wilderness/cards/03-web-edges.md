# 3 — Edge declarations in the server and the web Controls panel

Index entry: `tasks.md` task 3.

## Goal
Each side of a wilderness zone is declared as a mountain, a river or a
zoneline (the edge declarations). The human first-look pass (task 4) has to try
several of these combinations in the browser, but right now only the CLI
(task 2) can set them. Let the browser set them too.

## Done when
- [ ] `POST /api/generate` accepts an optional `edges` field (controls mode),
      e.g. `{"N": "zoneline", "E": "river"}`. An unknown side or type gives a
      400 that names the field, before anything is written (the M1 convention).
      → verify: tests in `tests/test_server.py`.
- [ ] The Controls panel shows four side selectors (mountain / river / zoneline)
      only when zone type = wilderness, and sends them with the request.
      → verify: `cd web; npx vite build` succeeds.
- [ ] Wilderness appears in the zone-type dropdown when the server runs with
      `EQ_S3D_DEV_WILDERNESS=1` (this comes free from task 2 via
      `/api/zone_types`; confirm it).
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Movement keys must be suppressed while a form field has focus
  (lessons-learned, Web viewer). The new selectors are form fields.
- Don't change `web/package.json`. The worktree shares `node_modules`.

## Result
<!-- worker: one line -->
