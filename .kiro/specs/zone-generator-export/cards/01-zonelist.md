# 1 — Known short names

Index entry: `tasks.md` task 1. Requirement 1.1. Design "Known short names"; decisions 2, 3.

## Goal
`analyzer/zonelist.py`: `KnownZone(shortname, long_name, container, in_install)`,
`DEFAULT_TARGET = "arena"`, `known_shortnames(eq_path=None)`, `is_known(name)` (case-insensitive),
`closest(name, n=5)`, and `python -m analyzer.zonelist --write`, which scans the install by the
umbrella's rules and writes `analyzer/data/rof2_zones.json`. The rules: a `.s3d` holding
`<stem>.wld`, or an `.eqg` holding a `.zon` or a `ter_*.ter`, or a loose `<stem>.zon` beside it;
companions dropped. Commit the written list. Long names: fill them if the install has a readable
source (say which in the commit), else leave them empty.

## Done when
- [x] The committed list holds `arena` and the classic zones (`qeynos`, `freporte`, `befallen`,
      `blackburrow`, `crushbone`) and no companion (`*_obj`, `*_chr`, `gequip*`). → verify: `python -m pytest tests/test_zonelist.py -q`
- [x] With no install configured every entry has `in_install` false; with `F:\everquest_rof2`
      `arena` is true (skip when the install is absent). Same command.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
The list holds names and container only: no client bytes. Never write under `EQ_PATH`. Don't read
`.env` yourself; find the install the way `ZoneInspector` does.

## Result
✔ 8624b5c · 3252 passed
