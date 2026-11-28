# P-B Traversable — decisions

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| 3 | Zone type availability is tied to the gate | A zone type is offered only once it passes; a prompt-planned disabled type is swapped visibly |
| 17 | Caves are a dungeon archetype, not a pipeline or a theme | M0 deleted the SDF cave pipeline and the `cave` theme; caves came back as the `cave` Purpose (step 21, P-E) and the rough wall style (step 8, P-E) |

## Slice decisions

| Slice | Where | Topics |
|---|---|---|
| M0 | [`zone-generator-m0-hygiene/tasks.md`](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) | the gate's adjacency made sound (true contact at matching height) |
| M1 | [`zone-generator-m1-controls-traversability/tasks.md`](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) (Decision 13: the one-time M1 seed break) | union-find walk surface, one router, corridor continuity, wilderness drape rejected |
| Step 7 | [`zone-generator-dungeon-verticality/archive.md`](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md) | the gate learns stairs and bridges first; floors only |
| Step 31 | [`zone-generator-district-races/archive.md`](../../../.kiro/specs/zone-generator-district-races/archive.md) (decision 14) | drops one-way, strong connectivity |
| Step 33 | [`zone-generator-layout-repair/archive.md`](../../../.kiro/specs/zone-generator-layout-repair/archive.md) | (in progress) |

## Settled (don't relitigate)

- The gate walks the mesh; the room graph is only the oracle of what should be reached.
- Structural tests passing is necessary, not sufficient: major geometry changes are looked at in
  3D (`docs/ACCEPTANCE.md`).
- Don't decimate walkable floors.
- Elevation uses subdivided ramps, not tall stairs, to stay under the 3 u step-up.
- The gate learns a new kind of geometry before a generator makes it.
- Same-axis room pairs get a Z-route, not an L (lessons-learned).
