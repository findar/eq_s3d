# 3 — Edge declarations in the server and the web Controls panel

Index entry: `tasks.md` task 3.

## Goal
Each side of a wilderness zone is declared as a mountain, a river or a
zoneline (the edge declarations). The human first-look pass (task 4) has to try
several of these combinations in the browser, but right now only the CLI
(task 2) can set them. Let the browser set them too.

## Done when
- [x] `POST /api/generate` accepts an optional `edges` field (controls mode),
      e.g. `{"N": "zoneline", "E": "river"}`. An unknown side or type gives a
      400 that names the field, before anything is written (the M1 convention).
      → verify: tests in `tests/test_server.py`.
- [x] The Controls panel shows four side selectors (mountain / river / zoneline)
      only when zone type = wilderness, and sends them with the request.
      → verify: `cd web; npx vite build` succeeds.
- [x] Wilderness appears in the zone-type dropdown when the server runs with
      `EQ_S3D_DEV_WILDERNESS=1` (this comes free from task 2 via
      `/api/zone_types`; confirm it).
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Movement keys must be suppressed while a form field has focus
  (lessons-learned, Web viewer). The new selectors are form fields.
- Don't change `web/package.json`. The worktree shares `node_modules`.

## Result
✔ branch `agent/wild-3` · 493 passed (also with the flag set in the shell) · frontend builds, no new tsc errors · edges ride in `controls.edges`. Not clicked through in a browser; task 4 is the first real use. Also added a session fixture in `tests/conftest.py` that clears `EQ_S3D_DEV_WILDERNESS`, so a suite run from the server's shell can't flip the disabled-wilderness tests.
