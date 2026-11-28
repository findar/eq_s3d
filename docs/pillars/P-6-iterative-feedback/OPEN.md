# P-6 Iterative feedback — open items

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

IDs are `P-6-<k>`. The columns are explained in [P-1's `OPEN.md`](../P-1-web-app/OPEN.md). Roll-up: [`OPEN.md`](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-6-1"></a>P-6-1 | `add_room`, `remove_room`, `add_region`, `remove_region`, `set_verticality` and `set_topology` answer "not yet supported" | [step 18 archive](../../../.kiro/specs/zone-generator-edits/archive.md) ([umbrella decision 37](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part A3) | open | code: [`generators/edits.py`](../../../generators/edits.py) 53 |
| <a id="p-6-2"></a>P-6-2 | A `rooms_seed` rebuild of an edited version drops its purpose and lock edits | [step 18 archive](../../../.kiro/specs/zone-generator-edits/archive.md) ([step 18 decision 10](../../../.kiro/specs/zone-generator-edits/archive.md#decisions)) | open | record |
| <a id="p-6-3"></a>P-6-3 | The edit tint is a disc on classic and city rooms; corridors aren't tinted | [step 18 archive](../../../.kiro/specs/zone-generator-edits/archive.md) | open | record |
| <a id="p-6-4"></a>P-6-4 | Not looked at in person: decor, lights, regions, lock points and city POIs after a resize; the tint; "the boss room" resolving to room_0 on a classic dungeon (not reproduced on 16 builds) | [step 18 archive](../../../.kiro/specs/zone-generator-edits/archive.md) | waiting | — |
| <a id="p-6-5"></a>P-6-5 | An edit removing rooms from a districted zone could leave a District's `room_ids` stale (latent until `remove_room` lands) | [step 20 archive](../../../.kiro/specs/zone-generator-districts/archive.md) | open | record |
| <a id="p-6-6"></a>P-6-6 | A contents seed: reroll a room's Structure and Clutter Features while keeping its layout (the decor seed covers Props only) | steps [9](../../../.kiro/specs/zone-generator-room-layouts/archive.md), [11](../../../.kiro/specs/zone-generator-room-decor/archive.md) and [12](../../../.kiro/specs/zone-generator-world-sockets/archive.md) archives | open | record |
| <a id="p-6-7"></a>P-6-7 | Users editing rule recipes from the page or a prompt | [step 6 archive](../../../.kiro/specs/zone-generator-graph-layout/archive.md) | open | — |
| <a id="p-6-8"></a>P-6-8 | **The authoring hand-off.** The [project README](../../../README.md) promises the output is "a starting point for a manual authoring pass", but nothing supports that pass. There is no export to an editing tool, no guide to what the sidecar's advisory data (pacing roles, Gates, POIs, hints) means or how to act on it, and no way to bring hand edits back as a new version. Door models ([P-3-11](../P-3-rof2-eqemu/OPEN.md#p-3-11)) and user docs ([P-9-1](../P-9-engineering/OPEN.md#p-9-1)) touch it but don't cover it | gap 2026-11-27 | open | code: no editor export in [`generators/export.py`](../../../generators/export.py) |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| `edit_outside_bands` waits on quality bands | `7466fef` ([step 19](../../../.kiro/specs/zone-generator-quality/tasks.md): the quality gate in the pipeline) |
| The rest of [M4](../../../.kiro/specs/zone-generator/design.md#delivery-plan) (Sessions, chat edits, undo and redo) | [step 18](../../../.kiro/specs/zone-generator-edits/tasks.md) ([umbrella decision 37](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)) |
| [M4](../../../.kiro/specs/zone-generator/design.md#delivery-plan)'s partial rebuild ([step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) "out of this step") | [step 16](../../../.kiro/specs/zone-generator-partial-rebuild/tasks.md) ([umbrella decision 35](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)) |
| A single-room decor view ([step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) backlog) | [step 15](../../../.kiro/specs/zone-generator-decor-rules/tasks.md) (room view) |
