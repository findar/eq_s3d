# Design — zone-generator-export (roadmap step 17)

Written at master `b005e80`. Verify against the code before you rely on a line here. The
umbrella design's "Known short names", "SQL export" and "Export" sections are the long form;
this file records where things are now and what changed.

## Where things are

- A build lives in `output/web/<zone>/v<n>/`: `<zone>.eqg`, `.glb`, `.zone.json`, `.map.svg`,
  `maps/<zone>.txt` (+ `_1`…`_3` when there are depth bands), and the step 12/16 hand-offs
  (`.request.json`, `.spec.json`, `.rooms.json`, `.world.json`, `.attach.json`).
- `core/pfs.py` `PfsArchive` (`from_file`, `files`, `add`, `get`); the CRC is EQ's own (see
  lessons-learned), computed on `add`. `core/zon.py` `ZonFile.from_bytes` / `to_bytes`; the
  first model is the terrain, `TER_<NAME>.TER`.
- `analyzer/rof2check.py` `check_eqg(eqg_path, spec, sidecar_path=, agent=)`: eleven checks,
  one of them that every name matches the Build_Name.
- `generators/zone_spec.py` `GateSpec` (`lock_x/y/z`, `corridor_id`, `tier`); Gates exist when
  Locks > 0. The sidecar's `gates` mirrors them.
- `server/app.py` serves build files at `/api/zones/<zone>/v<n>/<file>`; `main.py` has the
  `generate` subcommand (argparse, `sub.add_parser`).
- The install is at `EQ_PATH` (`.env`); `F:\everquest_rof2` here. `arena` there has
  `arena.s3d`, `arena_obj.s3d`, `arena_chr.s3d`, and also `arena.eqg` with a loose
  `arena.zon`: task 2 finds which one the client loads.

## Known short names (`analyzer/zonelist.py`)

As the umbrella, less the zone id (amendment A1). `analyzer/data/rof2_zones.json` is made once
by `python -m analyzer.zonelist --write` from the install scan (the umbrella's rules for what is
a zone archive and what is a companion), and committed. It holds short name, container and long
name (empty when unknown). `known_shortnames()` reads it and sets `in_install` from `EQ_PATH`
when one is configured; cached per process.

## Export (`generators/export.py`)

```python
def export_build(build_dir: Path, shortname: str | None = None, *,
                 clear_spawns: bool = False) -> ExportResult: ...
# ExportResult: shortname, dir, files, format (FormatReport), sql_written, warnings
```

Reads the build's `.eqg`; renames `ter_<name>.ter` and `<name>.zon`, sets the ZON's first model
to `TER_<SHORT>.TER`, adds every other entry unchanged (the CRC is recomputed for each name by
`PfsArchive.add`). Copies the map files under the new names and writes `<short>.zone.json` (the
build's sidecar plus `shortname` and the export's options). Runs `check_eqg` on the exported
archive with the short name as the expected name; on a failure it writes no SQL and no bundle.
Then `sqlexport.export_sql` and the bundle. Writes to `<build dir>/export/<short>/` only;
rewriting the same export replaces that folder's files.

## SQL (`generators/sqlexport.py`)

```python
def export_sql(spec: ZoneSpec, shortname: str, *, door_model: str,
               clear_spawns: bool = False, bounds_min_z: float) -> str: ...
```

- Header: comment lines naming the short name, saying the script changes an EXISTING zone and to
  back up the `zone`, `doors` (and with spawn cleanup `spawn2`, `grid`, `grid_entries`,
  `ground_spawns`) rows first.
- `START TRANSACTION;` … `COMMIT;` around:
  `UPDATE zone SET safe_x=…, safe_y=…, safe_z=…, underworld=… WHERE short_name='<short>' AND version=0;`
  `DELETE FROM doors WHERE zone='<short>' AND version=0;`
  one `INSERT INTO doors (doorid, zone, version, name, pos_x, pos_y, pos_z, heading, opentype, size, …)`
  per Gate, `doorid` by tier then id, position the lock, heading along its corridor.
- Only finite numbers (else no script, an error naming the field) and a short name from the
  Known_Zone_List go into a statement.
- The pinned columns (decision 4) are the EQEmu `doors` and `zone` repository columns at the
  time of writing; the test builds those tables in SQLite and applies the script.

## Doors

Task 2 decides from the install which Door model a takeover zone can name: a model the client
already loads for any zone (a global), or one packed into our `.eqg` by the build (task 5). The
SQL then names it. A door is a runtime record, never geometry (lessons-learned "Design calls");
a packed model is only something for the row to name.

## Server, CLI and page

- `GET /api/shortnames` → `{default, zones: [{shortname, long_name, container, in_install}]}`.
- `POST /api/export {zone, version, shortname?, clear_spawns?}` → the export's files' URLs and
  the format report; 400 for an unknown short name (with up to 5 close names), 404 for an
  unknown build. `GET /api/zones/<zone>/v<n>/export/<short>/<file>` serves the files, and
  `<short>.bundle.zip` is made on request.
- `main.py export <build dir> [--shortname] [--clear-spawns]`; an unknown name exits 2.
- The page: an **Export** row in the side panel's files section: the picker (filter, installed
  first, `arena` preselected), the spawn-cleanup tick, the takeover note, and **Export**, which
  then lists the bundle and the files.
