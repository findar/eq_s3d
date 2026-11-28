# P-3 Usable in RoF2 and EQEmu — decisions

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Umbrella decision numbers link to the umbrella design's
[Decisions Made in This Revision](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| [4](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | "RoF2-usable" has two tiers | Tier 1 an automated format check; Tier 2 minimal SQL plus a manual in-engine smoke load; spawns, loot and an automated in-engine loop are out |
| [15](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Short-name takeover is the install model | RoF2's zone list is client-side, so a zone takes over an existing short name, `arena` by default |
| [16](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | SQL updates the target's existing rows | `UPDATE zone … WHERE short_name`, replace its `doors`, optional spawn cleanup; never a new zone row |
| [20](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Target short name is chosen at Export, never at generation | Builds are named by their Build_Name; Export is a rename-only copy. Rejected: prompt detection (it mistakes `arena`, `hole`, `bazaar` for zone names) |
| [36](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 17](../../../.kiro/specs/zone-generator-export/tasks.md) delivers [M6](../../../.kiro/specs/zone-generator/design.md#delivery-plan)'s export | (A1) rows are addressed by short name, with no zone id; (A2) the bundled list is the install's names; (A3) a Gate's door stands across the doorway nearest the lock |

## Slice decisions

| Slice | Where |
|---|---|
| [Step 17](../../../.kiro/specs/zone-generator-export/tasks.md) | [`zone-generator-export/archive.md`](../../../.kiro/specs/zone-generator-export/archive.md) "Decisions" (among them [step 17 decision 5](../../../.kiro/specs/zone-generator-export/archive.md#decisions), what the zone row sets, and [step 17 decision 9](../../../.kiro/specs/zone-generator-export/archive.md#decisions), the door heading) |
| [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 6 | [`zone-generator-m1-controls-traversability/design.md`](../../../.kiro/specs/zone-generator-m1-controls-traversability/design.md) [Format_Checker](../../../.kiro/specs/zone-generator-m1-controls-traversability/design.md#format_checker-analyzerrof2checkpy-new) and [Build_Name naming](../../../.kiro/specs/zone-generator-m1-controls-traversability/design.md#build_name-artifact-naming-generatorsbuilderpy-coreeqgpy) |

## Settled (don't relitigate)

- Doors are runtime records (EQEmu `doors`), produced by the SQL, never baked into the mesh.
- The tool writes only under `output/`; installing is manual and reversible (back up first).
- EQG collision is per triangle; no binary space partitioning (BSP) tree is needed.
