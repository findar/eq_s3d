# P-H World — open items

Status and Checked as in [P-A's OPEN](../P-A-web-app/OPEN.md). Roll-up: [OPEN.md](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| H-1 | Multi-zone worlds and zone lines between zones | ROADMAP "Later candidates"; step 12 archive | waiting (the user's design review) | — |
| H-2 | The `door` Socket kind is reserved and nothing makes one | step 12 (decision 32) | open (needs H-1) | code: `generators/world.py` `KINDS` |
| H-3 | An exact Mouth Socket chosen by the World, and more than one dungeon in a World | step 12 archive (design question 1) | open | record |
| H-4 | `tunnel_doors` and `sidecar_block` still call `landscape_for` instead of reading the World, as do the helpers `_host_grid` and `_hill` (`build_outdoor_dungeon_ter` itself no longer does) | step 12 archive | open | code: `generators/outdoor_dungeon.py` 701, 723, 1142, 1193 |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| A build whose spec `world_of` can't remake fails | step 12 task 20 (`world_of` reads the spec's own Landform; struck in its archive) |
