# 6 — Route, bundle and CLI

Index entry: `tasks.md` task 6. Requirements 1.2, 4.1, 4.3, 4.4. Design "Server, CLI and page".

## Goal
The SQL call in `export_build`, `GET /api/shortnames`, `POST /api/export`, the export file route,
`<short>.bundle.zip` and `main.py export`. The bundle holds the archive, maps, SQL, sidecar and an
`INSTALL.txt` with task 2's install steps.

## Done when
- [ ] Through the route, export a build to `arena` and download every file and the bundle. The
      bundle holds the five parts, and `INSTALL.txt` names the files to move aside. An unknown
      name is a 400 with close names; an unknown build is a 404. Path segments are refused as the
      file route refuses them. → verify: `python -m pytest tests/test_export_route.py -q`
- [ ] `python main.py export <build dir>` writes the same export; an unknown name exits 2. Same command.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Validate names with `fullmatch` (lessons-learned). The bundle is built on request into the export
folder, never into the build's own files.

## Result
