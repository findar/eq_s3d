# P-8 World — open items

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

IDs are `P-8-<k>`. The columns are explained in [P-1's `OPEN.md`](../P-1-web-app/OPEN.md). Roll-up: [`OPEN.md`](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-8-1"></a>P-8-1 | Multi-zone worlds and zone lines between zones | [ROADMAP "Pick up here", "Later candidates"](../../../ROADMAP.md#-pick-up-here-next-session); [step 12 archive](../../../.kiro/specs/zone-generator-world-sockets/archive.md) | waiting (the user's design review) | — |
| <a id="p-8-2"></a>P-8-2 | The `door` Socket kind is reserved and nothing makes one | [step 12 archive](../../../.kiro/specs/zone-generator-world-sockets/archive.md) ([umbrella decision 32](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)) | open (needs [P-8-1](#p-8-1)) | code: [`generators/world.py`](../../../generators/world.py) `KINDS` |
| <a id="p-8-3"></a>P-8-3 | An exact Mouth Socket chosen by the World, and more than one dungeon in a World | [step 12 archive](../../../.kiro/specs/zone-generator-world-sockets/archive.md) (its design question 1) | open | record |
| <a id="p-8-4"></a>P-8-4 | `tunnel_doors` and `sidecar_block` still call `landscape_for` instead of reading the World, as do the helpers `_host_grid` and `_hill` (`build_outdoor_dungeon_ter` itself no longer does) | [step 12 archive](../../../.kiro/specs/zone-generator-world-sockets/archive.md) | open | code: [`generators/outdoor_dungeon.py`](../../../generators/outdoor_dungeon.py) 701, 723, 1142, 1193 |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| A build whose spec `world_of` can't remake fails | [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) task 20 (`world_of` reads the spec's own Landform; struck through in its archive) |
