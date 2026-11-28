# P-3 Usable in RoF2 and EQEmu — design (living)

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Checked against the code at master `c3d9b99` (2026-11-27, the commit that opened the project-docs spec). Format gotchas (the filename CRC, multi-chunk names, ZON
radians, the footer timestamp) are in
[lessons-learned "File formats"](../../../.kiro/steering/lessons-learned.md#file-formats).

## The archive a build writes

Every build is named by its **Build_Name** (the zone id `gen_<ts>_<hex>`, or the CLI name;
lowercase letters, digits and `_` only, checked before any write). `<name>.eqg` is a PFS archive holding:

| Entry | From |
|---|---|
| `ter_<name>.ter` | the TER: the whole mesh, per-triangle collision flags, materials (`core/ter.py`) |
| `<name>.zon` | the ZON: model reference `TER_<NAME>.TER`, objects (trees, Structures, Props), lights, regions (`core/zon.py`; rotations in radians, yaw first) |
| `*.dds` | textures: one per material, plus model textures |
| `veg_*.mod`, `site_*.mod`, stock `.mod` models | generated trees and Structures; Props copied unchanged from the user's install |

[`core/pfs.py`](../../../core/pfs.py) computes EQ's own filename CRC (big-endian, polynomial `0x04C11DB7`, over the name with its closing null byte)
and writes the time in the footer, so two writes differ in their last 4 bytes only.

## The format gate

[`analyzer/rof2check.py`](../../../analyzer/rof2check.py) `check_eqg` runs on every build attempt. It never raises: a fault becomes
a failed check naming its cause, and dependent checks are marked skipped. The checks:
`pfs_reads`, `required_files`, `ter_roundtrip`, `zon_roundtrip`, `zon_model_ref`,
`material_indices`, `diffuse_textures`, `collision_policy`, `safe_point`, `bounds_sane`,
`name_consistent`. The report rides in the sidecar as `format`.

## Export

[`generators/export.py`](../../../generators/export.py), `POST /api/export`, `main.py export --shortname <short>`:

1. The short name must be in the Known_Zone_List ([`analyzer/data/rof2_zones.json`](../../../analyzer/data/rof2_zones.json): 496 zone short
   names from a RoF2 install, long names from the client's zone table; the run-time scan of
   `EQ_PATH` only marks `in_install`). Default `arena`.
2. Rename, never rebuild: `<short>.eqg` with `ter_<short>.ter`, `<short>.zon` and the model
   reference `TER_<SHORT>.TER`; every other entry byte for byte. Maps and sidecar renamed too.
3. The renamed archive goes through the format gate with the short name expected.
4. Only on a pass: `<short>.sql` and `INSTALL.txt`; on request a `<short>.bundle.zip`.

Everything lands in `<build dir>/export/<short>/`; the build's own files are only read.

## The SQL

[`generators/sqlexport.py`](../../../generators/sqlexport.py) addresses rows by short name (`zone.short_name`, `doors.zone`), pinned
to the EQEmu columns as of 2026-11-16:

- `UPDATE zone` sets the safe point and `underworld` only; fog, clip planes, sky and `ztype` stay
  stock.
- `DELETE` then `INSERT` the target's `doors`: one door per Gate, standing across the doorway of
  its corridor nearest the lock (model `OBJ_BBDOOR1`, a stock door packed into builds with
  Gates; `lockpick` 32767, unpickable; key items are placeholders `990000 + tier`).
- With `clear_spawns`: deletes of that zone's `spawn2`, `grid` and ground-spawn rows, so stock
  NPCs don't stand in the new geometry.
- Never inserts a `zone` row. The script is text to review; the tool never runs it.

## What the tool does not produce

- EQEmu server-side files: `maps/base/<short>.map`, water maps (`.wtr`), navmeshes (`nav/`).
  The server falls back to no pathing and no water there.
- `.s3d` / WLD output: we read the Classic–PoP format but write only `.eqg`.
- Spawns, loot, factions, zone lines.
