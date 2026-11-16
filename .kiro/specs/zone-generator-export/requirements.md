# Requirements Document

> **STATUS: roadmap step 17, ready.** Drafted 2026-11-16 at master `b005e80`. The user said
> "Keep working and we can validate this in the next step" with step 16's human checks still
> open, so the lead chose the next step: umbrella milestone M6, the export (the last milestone
> not started). The user confirms the choice at the first look (task 8). Task index: `tasks.md`
> (card format). Decisions: `archive.md`.

## Introduction

A build today is a `gen_<ts>_<hex>.eqg` with map files and a sidecar. Nothing turns it into
something the RoF2 client or an EQEmu server can load: the client finds zones by short name,
and the server needs the zone row's safe point and doors. The umbrella spec designs this as an
**Export**: a copy of a build named for an existing short name it takes over (default `arena`),
a reviewable SQL script for that short name's server rows, and a bundle with install steps.

This step builds the umbrella's Requirement 8 (export-time short-name takeover) and
Requirement 10 (Tier-2 SQL export), with the amendments below, plus the Format_Checker's export
checks (umbrella Req 9.7, second half).

## Glossary

The umbrella glossary applies (Export, Target_Shortname, Known_Zone_List, Default_Target,
SQL_Exporter, Gate). Added here:

- **Takeover**: installing an Export over a stock zone: its client files moved aside, ours
  copied in, its server rows changed by the SQL.
- **Door model**: the model an EQEmu `doors` row names; the client draws it at the row's
  position.

## Amendments to the umbrella

- **A1 — No zone ids.** The SQL changes rows by `short_name` (the `zone` row) and by `zone`
  (the `doors` rows); it never needs `zoneidnumber`. So the Known_Zone_List carries no zone id
  (umbrella 8.1), the SQL header names the short name only (10.7), and 10.4's "or has no EQEmu
  zone id" is dropped.
- **A2 — Where the names come from.** The bundled Known_Zone_List is the set of zone short
  names found in a RoF2 install (names and container only, no client art), committed once; the
  install scan at run time only sets `in_install` (umbrella 8.2 stands). Long names are filled
  where a source gives them and empty otherwise.

## Requirements

### Requirement 1: Known short names

1. Umbrella 8.1–8.4, 8.7, 8.13, 8.14, as amended by A1 and A2.
2. `GET /api/shortnames` lists the entries and the Default_Target (`arena`).

### Requirement 2: The exported archive and files

1. Umbrella 8.10 (without the SQL and bundle, which are Requirement 3 and 4), 8.11, 8.12.
2. The Format_Checker runs on the exported archive (umbrella 9.7 second half); a failure writes
   no SQL and no bundle.
3. An Export never changes any file of the build, and exporting one build to two short names
   overwrites nothing of either.

### Requirement 3: The SQL script

1. Umbrella 10.1–10.3, 10.5–10.8, 10.10, as amended by A1.
2. The `zone` UPDATE also sets `underworld` below the build's lowest floor (decision 5), so a
   stock value above our geometry can't kill a player who walks in.
3. One `doors` row per Gate, at its lock, naming a Door model the client can draw in our zone
   (task 2 decides which); a build with no Gates gets the DELETE and no inserts.
4. Proven on an in-memory SQLite database of the pinned `zone`/`doors` columns (decision 4)
   holding stock rows: applying the script once or twice leaves the target's one row with our
   safe point and only our doors, and every other short name's rows unchanged.

### Requirement 4: Bundle and page

1. Umbrella 10.9: `<short>.bundle.zip` with the archive, the map files, the SQL, the sidecar and
   `INSTALL.txt`.
2. Umbrella 8.5: an Export action in the side panel's files section, with the short-name picker
   and the takeover note; a spawn-cleanup tick (default off).
3. Umbrella 8.8: an unknown short name is a 400 naming it and up to 5 close names.
4. The CLI: `python main.py export <build dir> [--shortname S] [--clear-spawns]`.

### Requirement 5: Nothing else changes

1. Every Generate is byte-identical to before (exports read builds, never write them), except
   where task 5 packs Door models into builds with Gates; those builds' new bytes are recorded
   in its commit.
