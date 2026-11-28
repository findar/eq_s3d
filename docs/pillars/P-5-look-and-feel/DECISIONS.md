# P-5 EverQuest look and feel — decisions

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Umbrella decision numbers link to the umbrella design's
[Decisions Made in This Revision](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| [8](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Conformance is measured and reported, not a retry gate | It depends on parameters, not seeds; enforced as a sweep property ([Property 38](../../../.kiro/specs/zone-generator/design.md#property-38-conformance-is-measured-and-in-range)). Not built ([P-5-2](OPEN.md#p-5-2)) |
| [12](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Normal maps are in scope | A separate DDS per material, named in the `e_TextureNormal0` material slot. Deferred by [umbrella decision 24](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) |
| [18](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Room shape vocabulary (captured, not a requirement) | Quarter-arc n-gon corners carving inward; superseded in practice by [umbrella decision 28](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)'s Outlines |
| [22](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Wilderness may carry generated trees | One `.mod` per species, placed as ZON objects; refines [ZG-Req-32.4](../../../.kiro/specs/zone-generator/requirements.md#requirement-32-settled-design-constraints) |
| [23](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 3](../../../.kiro/specs/zone-generator-placeholder-textures/tasks.md): diffuse preview and the UV convention | EQ's Direct3D convention measured on stock; `<Texture_Set>_<Surface>` names |
| [24](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 4](../../../.kiro/specs/zone-generator-interesting-textures/tasks.md): texture metrics, [ZG-Req-16](../../../.kiro/specs/zone-generator/requirements.md#requirement-16-procedural-normal-maps) deferred | Measured Texture_Profile per theme; normal maps stay planned because Classic–PoP has none (user's choice) |
| [28](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md): shaped walls | Outline inside the Box from Cells; replaces the [M5](../../../.kiro/specs/zone-generator/design.md#delivery-plan) natural-style sketch |
| [31](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 11](../../../.kiro/specs/zone-generator-room-decor/tasks.md): stock Props from the user's install | Catalogued, tagged, copied unchanged; needs `EQ_PATH`; refines [ZG-Req-32.4](../../../.kiro/specs/zone-generator/requirements.md#requirement-32-settled-design-constraints) and [ZG-Req-32.7](../../../.kiro/specs/zone-generator/requirements.md#requirement-32-settled-design-constraints) |
| [34](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 15](../../../.kiro/specs/zone-generator-decor-rules/tasks.md): decor rules as base plus layers; the room view | Layers ride beside the ZoneSpec, read only by Decor |
| [40](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 21](../../../.kiro/specs/zone-generator-cave/tasks.md): the `cave` Purpose | The look is the measured `rough` style, not the planned [M5](../../../.kiro/specs/zone-generator/design.md#delivery-plan) natural style; cave words choose the Purpose |
| [42](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 23](../../../.kiro/specs/zone-generator-winding-tunnels/tasks.md): rough corridors wind | Plain legs along a centreline, into measured clearance only; numbers from 113 stock tunnels |
| [43](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 25](../../../.kiro/specs/zone-generator-winding-routes/tasks.md): wind door to door | One centreline replaces the legs where it fits; `CorridorSpec.path`; cave rooms sit 4 corridor widths apart instead of 9 |
| [44](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 26](../../../.kiro/specs/zone-generator-winding-control/tasks.md): the Winding scalar; caves off the lattice | 0..2, default 1; cave zones changed at every setting (the user's choice) |
| [46](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 29](../../../.kiro/specs/zone-generator-cave-clumps/tasks.md): cave throats and clumps | ~0.33 of level cave Graph edges are throats; decor refuses a Prop that would leave the gate's core in a hollow |

## Slice decisions

| Slice | Where |
|---|---|
| [Step 1](../../../.kiro/specs/zone-generator-wilderness/tasks.md) | [`zone-generator-wilderness/archive.md`](../../../.kiro/specs/zone-generator-wilderness/archive.md) |
| [Step 2](../../../.kiro/specs/zone-generator-wilderness-trees/tasks.md) | [`zone-generator-wilderness-trees/archive.md`](../../../.kiro/specs/zone-generator-wilderness-trees/archive.md) |
| [Step 3](../../../.kiro/specs/zone-generator-placeholder-textures/tasks.md) | [`zone-generator-placeholder-textures/archive.md`](../../../.kiro/specs/zone-generator-placeholder-textures/archive.md) |
| [Step 4](../../../.kiro/specs/zone-generator-interesting-textures/tasks.md) | [`zone-generator-interesting-textures/archive.md`](../../../.kiro/specs/zone-generator-interesting-textures/archive.md) |
| [Step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md) | [`zone-generator-room-walls/archive.md`](../../../.kiro/specs/zone-generator-room-walls/archive.md) |
| [Step 11](../../../.kiro/specs/zone-generator-room-decor/tasks.md) | [`zone-generator-room-decor/archive.md`](../../../.kiro/specs/zone-generator-room-decor/archive.md) |
| [Step 15](../../../.kiro/specs/zone-generator-decor-rules/tasks.md) | [`zone-generator-decor-rules/archive.md`](../../../.kiro/specs/zone-generator-decor-rules/archive.md) |
| [Step 21](../../../.kiro/specs/zone-generator-cave/tasks.md) | [`zone-generator-cave/archive.md`](../../../.kiro/specs/zone-generator-cave/archive.md) |
| Steps [23](../../../.kiro/specs/zone-generator-winding-tunnels/tasks.md), [24](../../../.kiro/specs/zone-generator-flooded-rooms/tasks.md), [25](../../../.kiro/specs/zone-generator-winding-routes/tasks.md), [26](../../../.kiro/specs/zone-generator-winding-control/tasks.md) and [29](../../../.kiro/specs/zone-generator-cave-clumps/tasks.md) | [`winding-tunnels`](../../../.kiro/specs/zone-generator-winding-tunnels/archive.md), [`flooded-rooms`](../../../.kiro/specs/zone-generator-flooded-rooms/archive.md), [`winding-routes`](../../../.kiro/specs/zone-generator-winding-routes/archive.md), [`winding-control`](../../../.kiro/specs/zone-generator-winding-control/archive.md), [`cave-clumps`](../../../.kiro/specs/zone-generator-cave-clumps/archive.md) |

## Settled (don't relitigate)

- voxel ≈ 12 u matches Classic–PoP triangle size (~12–14 u median edge).
- No bespoke trained mesh model for the core.
- Grid-and-rule-tile rooms read as modern roguelike; not used.
- Classic–PoP is the default look; later-era art is opt-in at most.
