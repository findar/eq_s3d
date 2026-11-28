# P-F Iterative feedback — open items

Status and Checked as in [P-A's OPEN](../P-A-web-app/OPEN.md). Roll-up: [OPEN.md](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| F-1 | `add_room`, `remove_room`, `add_region`, `remove_region`, `set_verticality` and `set_topology` answer "not yet supported" | step 18 (decision 37 A3) | open | code: `generators/edits.py` 53 |
| F-2 | A `rooms_seed` rebuild of an edited version drops its purpose and lock edits | step 18 archive (its decision 10) | open | record |
| F-3 | The edit tint is a disc on classic and city rooms; corridors aren't tinted | step 18 archive | open | record |
| F-4 | Not looked at in person: decor, lights, regions, lock points and city POIs after a resize; the tint; "the boss room" resolving to room_0 on a classic dungeon (not reproduced on 16 builds) | step 18 archive | waiting | — |
| F-5 | An edit removing rooms from a districted zone could leave a District's `room_ids` stale (latent until `remove_room` lands) | step 20 archive | open | record |
| F-6 | A contents seed: reroll a room's Structure and Clutter Features while keeping its layout (the decor seed covers Props only) | steps 9, 11, 12 archives | open | record |
| F-7 | Users editing rule recipes from the page or a prompt | step 6 archive | open | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| `edit_outside_bands` waits on quality bands | `7466fef` (step 19: the quality gate in the pipeline) |
| The rest of M4 (Sessions, chat edits, undo/redo) | step 18 (decision 37) |
| M4's partial rebuild (step 12 "out of this step") | step 16 (decision 35) |
| A single-room decor view (step 13 backlog) | step 15 (room view) |
