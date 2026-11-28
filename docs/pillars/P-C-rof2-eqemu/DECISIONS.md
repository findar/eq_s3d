# P-C Usable in RoF2 and EQEmu — decisions

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| 4 | "RoF2-usable" has two tiers | Tier 1 an automated format check; Tier 2 minimal SQL plus a manual in-engine smoke load; spawns, loot and an automated in-engine loop are out |
| 15 | Short-name takeover is the install model | RoF2's zone list is client-side, so a zone takes over an existing short name, `arena` by default |
| 16 | SQL updates the target's existing rows | `UPDATE zone … WHERE short_name`, replace its `doors`, optional spawn cleanup; never a new zone row |
| 20 | Target short name is chosen at Export, never at generation | Builds are named by their Build_Name; Export is a rename-only copy. Rejected: prompt detection (it mistakes `arena`, `hole`, `bazaar` for zone names) |
| 36 | Step 17 delivers M6's export | A1 rows addressed by short name, no zone id; A2 the bundled list is the install's names; A3 a Gate's door stands across the doorway nearest the lock |

## Slice decisions

| Slice | Where |
|---|---|
| Step 17 | [`zone-generator-export/archive.md`](../../../.kiro/specs/zone-generator-export/archive.md) "Decisions" (incl. 5: what the zone row sets; 9: door heading) |
| M1 wave 6 | [`zone-generator-m1-controls-traversability/design.md`](../../../.kiro/specs/zone-generator-m1-controls-traversability/design.md) "Format_Checker", Build_Name naming |

## Settled (don't relitigate)

- Doors are runtime records (EQEmu `doors`), produced by the SQL, never baked into the mesh.
- The tool writes only under `output/`; installing is manual and reversible (back up first).
- EQG collision is per triangle; no BSP tree is needed.
