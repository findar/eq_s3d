# P-3 Usable in RoF2 and EQEmu — open items

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

IDs are `P-3-<k>`. The columns are explained in [P-1's `OPEN.md`](../P-1-web-app/OPEN.md). Roll-up: [`OPEN.md`](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-3-1"></a>P-3-1 | **No in-client proof.** No exported zone has been zoned into in RoF2 ("Loaded arena.EQG." in `Logs\dbg.txt`), no SQL applied to an EQEmu server; the in-client map window ([umbrella decision 21](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)c) is unproven too | [step 17 archive](../../../.kiro/specs/zone-generator-export/archive.md); gap 2026-11-27 | waiting (needs the user at the client) | record |
| <a id="p-3-2"></a>P-3-2 | Door swing direction and hinge side unchecked in the client | [step 17 archive](../../../.kiro/specs/zone-generator-export/archive.md) | waiting | record |
| <a id="p-3-3"></a>P-3-3 | The `.eqg` object rotation direction unchecked in the client | [step 11 archive](../../../.kiro/specs/zone-generator-room-decor/archive.md) | waiting | record |
| <a id="p-3-4"></a>P-3-4 | The zone row sets only the safe point and `underworld`; fog, clip planes, sky and `ztype` stay stock; [umbrella decision 19](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)'s mapping of zone type + enclosure onto `ztype`, sky and outdoor flags not done | [step 17 archive](../../../.kiro/specs/zone-generator-export/archive.md) ([step 17 decision 5](../../../.kiro/specs/zone-generator-export/archive.md#decisions)); [umbrella decision 19](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | open | code: [`generators/sqlexport.py`](../../../generators/sqlexport.py) |
| <a id="p-3-5"></a>P-3-5 | Key items are placeholders (990000 + tier) for the user to replace | [step 17 archive](../../../.kiro/specs/zone-generator-export/archive.md) | parked | code |
| <a id="p-3-6"></a>P-3-6 | **EQEmu server-side files** not produced: server map (`maps/base/<short>.map`), water map, navmesh | gap 2026-11-27 | open | code: no writer |
| <a id="p-3-7"></a>P-3-7 | **Spawns**: nothing populates the zone; only optional deletion of the stock spawn rows (out of scope by [umbrella decision 4](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision); the user may want a starter set) | gap 2026-11-27 | waiting (scope call) | code |
| <a id="p-3-8"></a>P-3-8 | **Client art in exports**: a build with Decor packs models copied from the user's install, so its `.eqg` is for the user's own client and server only; nothing marks or strips that on Export | gap 2026-11-27; [umbrella decision 31](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | waiting (policy call) | code |
| <a id="p-3-9"></a>P-3-9 | **`.s3d` era output**: the default Classic–PoP look ships as `.s3d`/WLD in the real game, but we write only `.eqg` | gap 2026-11-27; north-star rule 2 | waiting (wanted?) | code: [`core/wld.py`](../../../core/wld.py) is read-only |
| <a id="p-3-10"></a>P-3-10 | Hand-renaming exported files to install over a different short name: whether client and server accept it | [umbrella decision 15](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) (its follow-up) | waiting (needs the client) | — |
| <a id="p-3-11"></a>P-3-11 | Doorway-fit: catalogue RoF2 door models by theme and footprint and snap gated openings to one; today every door is `BBDOOR1` | [ROADMAP "Design work captured"](../../../ROADMAP.md#design-work-captured-not-yet-built) | open | code: [`generators/sqlexport.py`](../../../generators/sqlexport.py) |
| <a id="p-3-12"></a>P-3-12 | **Client performance** not measured: frame rate, draw calls and triangle count of a decorated zone in the client | gap 2026-11-27 | open | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| No short-name concept; files named by an internal id ([umbrella Known Limitation 9](../../../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them)) | merge `17c1b94` ([M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 6: Build_Name naming, the format gate, confinement); [step 17](../../../.kiro/specs/zone-generator-export/tasks.md) Export (closed by `be4d04e`, the step 17 close-out docs) |
| The [M6](../../../.kiro/specs/zone-generator/design.md#delivery-plan) SQL export (listed in [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) as "out of this step") | [step 17](../../../.kiro/specs/zone-generator-export/tasks.md) |
| Doorway gates as doors at room openings (steps [11](../../../.kiro/specs/zone-generator-room-decor/tasks.md), [12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md)) | [step 17](../../../.kiro/specs/zone-generator-export/tasks.md): one `doors` row per Gate ([umbrella decision 36](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part A3); the door model catalogue stays open as [P-3-11](#p-3-11) |
