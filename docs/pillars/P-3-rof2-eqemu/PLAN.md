# P-3 Usable in RoF2 and EQEmu — plan

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

## Goal

A generated zone loads in the RoF2 client and can be entered on an EQEmu server. Because the
client's zone list is fixed, a zone is installed by taking over an existing short name; the
tool writes the files named for that zone and a reviewable SQL script, and the user copies them
in by hand.

## Scope

- Binary formats and their round-trips ([`core/`](../../../core): PFS, TER, ZON, EQG, WLD reading).
- The Tier-1 format gate ([`analyzer/rof2check.py`](../../../analyzer/rof2check.py)) in every build.
- Export ([`generators/export.py`](../../../generators/export.py)), the known short-name list ([`analyzer/zonelist.py`](../../../analyzer/zonelist.py)), the
  EQEmu SQL ([`generators/sqlexport.py`](../../../generators/sqlexport.py)), the bundle and `INSTALL.txt`.
- Proof in the client and on a server (manual, [`docs/ACCEPTANCE.md` "Step 17 — Export"](../../ACCEPTANCE.md#step-17--export)).

## Non-goals

- Writing into the EQ install or applying SQL: always the user's manual step ([ZG-Req-31](../../../.kiro/specs/zone-generator/requirements.md#requirement-31-file-system-confinement)).
- An automated in-engine test loop (needs a running server; [umbrella decision 4](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)).
- NPC spawns and loot ([umbrella decision 4](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision); [P-3-7](OPEN.md#p-3-7) holds the open question).

## Requirements

| ID | Requirement | Parent | Status now |
|---|---|---|---|
| <a id="p-3-req-1"></a>P-3-Req-1 | At Export, a build takes over an existing short name | [ZG-Req-8](../../../.kiro/specs/zone-generator/requirements.md#requirement-8-export-time-short-name-takeover) | Built ([step 17](../../../.kiro/specs/zone-generator-export/tasks.md)): a rename-only copy to `export/<short>/`, 496 known names, `arena` by default |
| <a id="p-3-req-2"></a>P-3-Req-2 | Every build passes the Tier 1 RoF2 format check | [ZG-Req-9](../../../.kiro/specs/zone-generator/requirements.md#requirement-9-tier-1-rof2-format-check) | Built ([M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 6; [step 17](../../../.kiro/specs/zone-generator-export/tasks.md) re-checks every Export): 11 named checks. There is no normal-map check, because there are no normal maps |
| <a id="p-3-req-3"></a>P-3-Req-3 | Tier 2: EQEmu SQL that points the short name's database rows at the zone | [ZG-Req-10](../../../.kiro/specs/zone-generator/requirements.md#requirement-10-tier-2-eqemu-sql-export) | Built ([step 17](../../../.kiro/specs/zone-generator-export/tasks.md)): `UPDATE zone` (safe point, `underworld`), the `doors` rows replaced, optional spawn cleanup. The manual load in the game has never been done ([P-3-1](OPEN.md#p-3-1)) |
| <a id="p-3-req-4"></a>P-3-Req-4 | Every file reader and writer round-trips | [ZG-Req-11](../../../.kiro/specs/zone-generator/requirements.md#requirement-11-format-and-ir-round-trips) | Built ([M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md)'s properties for PFS, the filename CRC, TER, ZON and the ZoneSpec) |

## Traceability

Which slices served each requirement. ([`scripts/task_status.py`](../../../scripts/task_status.py)
will generate this table after [project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md).)

| Requirement | Served by |
|---|---|
| [P-3-Req-1](#p-3-req-1) | [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 6 (Build_Name), [step 17](../../../.kiro/specs/zone-generator-export/tasks.md) |
| [P-3-Req-2](#p-3-req-2) | [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 6, [step 17](../../../.kiro/specs/zone-generator-export/tasks.md) |
| [P-3-Req-3](#p-3-req-3) | [step 17](../../../.kiro/specs/zone-generator-export/tasks.md) |
| [P-3-Req-4](#p-3-req-4) | pre-spec Phase 1, [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Phase 1 (pre-spec, [ROADMAP](../../../ROADMAP.md#phase-1--core-io)) | — | done | (before specs) | PFS read/write with EQ's CRC, TER/ZON serialisers, EQG assembler; WLD reader |
| 17 | [`zone-generator-export`](../../../.kiro/specs/zone-generator-export/tasks.md) | done 2026-11-17, acceptance skipped at the user's word | 27 | Export under a known short name, SQL, bundle, `INSTALL.txt` |

Also served by: [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) (round-trip properties; P-9), [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 6 (Build_Name naming, the
format gate, output confinement; P-2), [step 2](../../../.kiro/specs/zone-generator-wilderness-trees/tasks.md) (`.mod` trees and ZON objects in the archive; P-5),
[step 3](../../../.kiro/specs/zone-generator-placeholder-textures/tasks.md) (shader `Opaque_MaxCB1.fx`; P-5), [step 11](../../../.kiro/specs/zone-generator-room-decor/tasks.md) (stock Props packed, ZON lights; P-5).

## The gap this pillar most needs closed

No generated zone has ever been loaded in the client or entered on a server. Every format
claim rests on our own reader and the format gate. [P-3-1](OPEN.md#p-3-1) is the single most valuable open item in
the project; it needs the user at the client.
