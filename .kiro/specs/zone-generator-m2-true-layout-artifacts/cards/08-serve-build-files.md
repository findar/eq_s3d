# 8 — Serve build files under `maps/`, HEAD, and artifact URLs

Index entry: `tasks.md` task 8. Design: "Server". Requirement 9.

## Goal
The server serves `/api/zones/{zone_id}/{version}/maps/{filename}` as well as
the flat route, answers HEAD on both, and lists every artifact's URL in the
generate response.

## Done when
- [ ] One handler serves both routes for GET and HEAD, with the media types in
      the design. A missing file gives 404. A bad segment, `..`, a disallowed
      extension or a path outside the build dir gives 400 with no content.
- [ ] Property 18 (build-file paths are served or refused by the rules) holds on
      200 examples against one pre-built directory.
- [ ] `GenerateResponse.artifacts` lists `map_svg`, `eqg`, `glb`, `sidecar` and
      every `eqmap` file (with `layer`), and each URL GETs 200. `map_url` and
      `eqg_url` stay.
      → verify: `python -m pytest tests/test_server.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Every 400 comes before any file read. The existing traversal-guard and
  allow-list tests must pass unchanged.

## Result
