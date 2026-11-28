# P-4 True-layout artifacts — open items

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

IDs are `P-4-<k>`. The columns are explained in [P-1's `OPEN.md`](../P-1-web-app/OPEN.md). Roll-up: [`OPEN.md`](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-4-1"></a>P-4-1 | The map's "return" marks are inferred (`drop_returns` isn't saved in the spec) | [step 31 archive](../../../.kiro/specs/zone-generator-district-races/archive.md) | in flight ([step 32](../../../.kiro/specs/zone-generator-races-followups/tasks.md) task 3) | — |
| <a id="p-4-2"></a>P-4-2 | A wrapping District's hull overlaps its neighbour; a District label can sit under the legend | steps [20](../../../.kiro/specs/zone-generator-districts/archive.md), [31](../../../.kiro/specs/zone-generator-district-races/archive.md) archives | open | record |
| <a id="p-4-3"></a>P-4-3 | A map whose outline trace fails gets no layers | [step 31 archive](../../../.kiro/specs/zone-generator-district-races/archive.md) | open | record |
| <a id="p-4-4"></a>P-4-4 | A box build with an extra depth band: a 30-room moderate dungeon at seed 403 has 4 bands on 3 Levels (test `test_elevated_box_builds_have_one_band`; a layout problem older than [step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md)) | [step 13 archive](../../../.kiro/specs/zone-generator-site-sockets/archive.md) | open | record |
| <a id="p-4-5"></a>P-4-5 | The in-client map window has never shown one of our `.txt` files | [umbrella decision 21](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part c | waiting (on [P-3-1](../P-3-rof2-eqemu/OPEN.md#p-3-1)) | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| The map is a spec schematic, not the real walls ([umbrella Known Limitation 8](../../../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them)) | [step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md) (closed by merge `a97231a`, step 1b task 11: the release task) |
| Map outline depends on face order (`test_canonical_outline`, steps [9](../../../.kiro/specs/zone-generator-room-layouts/tasks.md) and [10](../../../.kiro/specs/zone-generator-wilderness-pois/tasks.md)) | `0af5124` (the outline no longer depends on face order) |
| The page's Socket markers infer the map's world-to-pixel mapping from room labels ([step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md)) | `bd394c6` ([step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) task 9: the map SVG carries its frame) |
