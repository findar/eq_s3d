# 3 — The exported archive and files

Index entry: `tasks.md` task 3. Requirement 2. Design "Export".

## Goal
`generators/export.py` `export_build(build_dir, shortname=None, clear_spawns=False)`: the renamed
archive, map files and sidecar in `<build dir>/export/<short>/`, checked by `check_eqg` with the
short name as the expected name. Extend `analyzer/rof2check.py` so the expected name can be
given; its build-time behaviour stays unchanged. Leave the SQL and bundle to tasks 4 and 6
(`sql_written` false until then).

## Done when
- [ ] Export a dungeon, a city, an outdoor dungeon and a wilderness to `arena` and to a second
      name. Entry names, ZON terrain reference and CRCs are as umbrella 8.10, and every other
      entry is byte-identical. Read back, each has the same vertices, polygons, materials,
      lights and regions (8.11). The build's files are unchanged by hash, and the two exports
      are apart (8.12). → verify: `python -m pytest tests/test_export.py -q`
- [ ] An unknown name raises an error naming it and up to 5 close names; a blank name is `arena`;
      `ARENA` is `arena`. Same command.
- [ ] Every build-time format check is unchanged. → verify: the rof2check tests (`python -m pytest tests/ -q -k rof2`)
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Use `PfsArchive.add` so each CRC is EQ's own for the new name (lessons-learned "PFS CRC"). The
footer time differs between two writes (lessons-learned): compare entries, not files.

## Result
✔ 2937141 · 3281 passed
