# P-C Usable in RoF2 and EQEmu — plan

## Goal

A generated zone loads in the RoF2 client and can be entered on an EQEmu server. Because the
client's zone list is fixed, a zone is installed by taking over an existing short name; the
tool writes the files named for that zone and a reviewable SQL script, and the user copies them
in by hand.

## Scope

- Binary formats and their round-trips (`core/`: PFS, TER, ZON, EQG, WLD reading).
- The Tier-1 format gate (`analyzer/rof2check.py`) in every build.
- Export (`generators/export.py`), the known short-name list (`analyzer/zonelist.py`), the
  EQEmu SQL (`generators/sqlexport.py`), the bundle and `INSTALL.txt`.
- Proof in the client and on a server (manual, `docs/ACCEPTANCE.md` "Step 17 — Export").

## Non-goals

- Writing into the EQ install or applying SQL: always the user's manual step (Req 31).
- An automated in-engine test loop (needs a running server; umbrella decision 4).
- NPC spawns and loot (umbrella decision 4; see OPEN C-7 for the open question).

## Requirements (umbrella IDs)

| ID | Requirement | Status now |
|---|---|---|
| P-C.8 | Export-time short-name takeover | Built (step 17): rename-only copy to `export/<short>/`, 496 known names, default `arena` |
| P-C.9 | Tier-1 RoF2 format check on every build | Built (M1 wave 6, step 17's Export checks): 11 named checks; no normal-map check (there are no normal maps) |
| P-C.10 | Tier-2 EQEmu SQL that points the short name's rows at the zone | Built (step 17): `UPDATE zone` (safe point, `underworld`), `doors` replaced, optional spawn cleanup. The in-engine smoke load has never been done (OPEN C-1) |
| P-C.11 | Every reader and writer round-trips | Built (M0 properties: PFS, CRC, TER, ZON, ZoneSpec) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Phase 1 (pre-spec) | — | done | (pre-spec) | PFS read/write with EQ's CRC, TER/ZON serialisers, EQG assembler; WLD reader |
| 17 | [`zone-generator-export`](../../../.kiro/specs/zone-generator-export/tasks.md) | done 2026-11-17, acceptance skipped at the user's word | 27 | Export under a known short name, SQL, bundle, `INSTALL.txt` |

Also served by: M0 (round-trip properties; Engineering), M1 wave 6 (Build_Name naming, the
format gate, output confinement; P-B), step 2 (`.mod` trees and ZON objects in the archive; P-E),
step 3 (shader `Opaque_MaxCB1.fx`; P-E), step 11 (stock Props packed, ZON lights; P-E).

## The gap this pillar most needs closed

No generated zone has ever been loaded in the client or entered on a server. Every format
claim rests on our own reader and the format gate. C-1 is the single most valuable open item in
the project; it needs the user at the client.
