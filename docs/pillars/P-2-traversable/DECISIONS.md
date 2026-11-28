# P-2 Traversable — decisions

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Umbrella decision numbers link to the umbrella design's
[Decisions Made in This Revision](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| [3](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Zone type availability is tied to the gate | A zone type is offered only once it passes; a prompt-planned disabled type is swapped visibly |
| [17](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Caves are a dungeon archetype, not a pipeline or a theme | [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) deleted the signed-distance-field cave pipeline and the `cave` theme; caves came back as the `cave` Purpose ([step 21](../../../.kiro/specs/zone-generator-cave/tasks.md), P-5) and the rough wall style ([step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md), P-5) |

## Slice decisions

| Slice | Where | Topics |
|---|---|---|
| [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) | [`zone-generator-m0-hygiene/tasks.md`](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) | the gate's adjacency made sound (true contact at matching height) |
| [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) | [`zone-generator-m1-controls-traversability/tasks.md`](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) ([M1 design decision 13](../../../.kiro/specs/zone-generator-m1-controls-traversability/design.md): the one-time M1 seed break) | union-find walk surface, one router, corridor continuity, wilderness drape rejected |
| [Step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) | [`zone-generator-dungeon-verticality/archive.md`](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md) | the gate learns stairs and bridges first; floors only |
| [Step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) | [`zone-generator-district-races/archive.md`](../../../.kiro/specs/zone-generator-district-races/archive.md) ([step 31 decision 14](../../../.kiro/specs/zone-generator-district-races/archive.md#decisions)) | drops one-way, strong connectivity |
| [Step 33](../../../.kiro/specs/zone-generator-layout-repair/tasks.md) | [`zone-generator-layout-repair/archive.md`](../../../.kiro/specs/zone-generator-layout-repair/archive.md) | (in progress) |

## Settled (don't relitigate)

- The gate walks the mesh; the room graph is only the oracle of what should be reached.
- Structural tests passing is necessary, not sufficient: major geometry changes are looked at in
  3D ([`docs/ACCEPTANCE.md`](../../ACCEPTANCE.md)).
- Don't decimate walkable floors.
- Elevation uses subdivided ramps, not tall stairs, to stay under the 3 u step-up.
- The gate learns a new kind of geometry before a generator makes it.
- Same-axis room pairs get a Z-route, not an L ([lessons-learned](../../../.kiro/steering/lessons-learned.md#geometry--fields)).
