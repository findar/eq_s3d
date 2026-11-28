# P-E EverQuest look and feel — decisions

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| 8 | Conformance is measured and reported, not a retry gate | It depends on parameters, not seeds; enforced as a sweep property (P38). Not built (OPEN E-2) |
| 12 | Normal maps are in scope | Separate DDS per material via `e_TextureNormal0`. Deferred by decision 24 |
| 18 | Room shape vocabulary (captured, not a requirement) | Quarter-arc n-gon corners carving inward; superseded in practice by decision 28's Outlines |
| 22 | Wilderness may carry generated trees | One `.mod` per species, ZON objects; refines Req 32.4 |
| 23 | Step 3: diffuse preview and the UV convention | EQ's Direct3D convention measured on stock; `<Texture_Set>_<Surface>` names |
| 24 | Step 4: texture metrics, Req 16 deferred | Measured Texture_Profile per theme; normal maps stay planned because Classic–PoP has none (user's choice) |
| 28 | Step 8: shaped walls | Outline inside the Box from Cells; replaces the M5 natural-style sketch |
| 31 | Step 11: stock Props from the user's install | Catalogued, tagged, copied unchanged; needs `EQ_PATH`; refines Req 32.4 and 32.7 |
| 34 | Step 15: decor rules as base plus layers; the room view | Layers ride beside the ZoneSpec, read only by Decor |
| 40 | Step 21: the `cave` Purpose | The look is the measured `rough` style, not the Natural_Style; cave words choose the Purpose |
| 42 | Step 23: rough corridors wind | Plain legs along a centreline, into measured clearance only; numbers from 113 stock tunnels |
| 43 | Step 25: wind door to door | One centreline replaces the legs where it fits; `CorridorSpec.path`; cave run 9 → 4 widths |
| 44 | Step 26: the Winding scalar; caves off the lattice | 0..2, default 1; cave zones changed at every setting (the user's choice) |
| 46 | Step 29: cave throats and clumps | ~0.33 of level cave Graph edges are throats; decor refuses a Prop that would leave the gate's core in a hollow |

## Slice decisions

| Slice | Where |
|---|---|
| Step 1 | [`zone-generator-wilderness/archive.md`](../../../.kiro/specs/zone-generator-wilderness/archive.md) |
| Step 2 | [`zone-generator-wilderness-trees/archive.md`](../../../.kiro/specs/zone-generator-wilderness-trees/archive.md) |
| Step 3 | [`zone-generator-placeholder-textures/archive.md`](../../../.kiro/specs/zone-generator-placeholder-textures/archive.md) |
| Step 4 | [`zone-generator-interesting-textures/archive.md`](../../../.kiro/specs/zone-generator-interesting-textures/archive.md) |
| Step 8 | [`zone-generator-room-walls/archive.md`](../../../.kiro/specs/zone-generator-room-walls/archive.md) |
| Step 11 | [`zone-generator-room-decor/archive.md`](../../../.kiro/specs/zone-generator-room-decor/archive.md) |
| Step 15 | [`zone-generator-decor-rules/archive.md`](../../../.kiro/specs/zone-generator-decor-rules/archive.md) |
| Step 21 | [`zone-generator-cave/archive.md`](../../../.kiro/specs/zone-generator-cave/archive.md) |
| Steps 23, 24, 25, 26, 29 | [`winding-tunnels`](../../../.kiro/specs/zone-generator-winding-tunnels/archive.md), [`flooded-rooms`](../../../.kiro/specs/zone-generator-flooded-rooms/archive.md), [`winding-routes`](../../../.kiro/specs/zone-generator-winding-routes/archive.md), [`winding-control`](../../../.kiro/specs/zone-generator-winding-control/archive.md), [`cave-clumps`](../../../.kiro/specs/zone-generator-cave-clumps/archive.md) |

## Settled (don't relitigate)

- voxel ≈ 12 u matches Classic–PoP triangle size (~12–14 u median edge).
- No bespoke trained mesh model for the core.
- Grid-and-rule-tile rooms read as modern roguelike; not used.
- Classic–PoP is the default look; later-era art is opt-in at most.
