# P-C Usable in RoF2 and EQEmu — open items

Status and Checked as in [P-A's OPEN](../P-A-web-app/OPEN.md). Roll-up: [OPEN.md](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| C-1 | **No in-client proof.** No exported zone has been zoned into in RoF2 ("Loaded arena.EQG." in `Logs\dbg.txt`), no SQL applied to an EQEmu server; the in-client map window (umbrella decision 21c) is unproven too | step 17 archive; gap 2026-11-27 | waiting (needs the user at the client) | record |
| C-2 | Door swing direction and hinge side unchecked in the client | step 17 archive | waiting | record |
| C-3 | The `.eqg` object rotation direction unchecked in the client | step 11 archive | waiting | record |
| C-4 | The zone row sets only the safe point and `underworld`; fog, clip planes, sky and `ztype` stay stock; decision 19's mapping of zone type + enclosure onto `ztype`, sky and outdoor flags not done | step 17 archive (decision 5); umbrella decision 19 | open | code: `generators/sqlexport.py` |
| C-5 | Key items are placeholders (990000 + tier) for the user to replace | step 17 archive | parked | code |
| C-6 | **EQEmu server-side files** not produced: server map (`maps/base/<short>.map`), water map, navmesh | gap 2026-11-27 | open | code: no writer |
| C-7 | **Spawns**: nothing populates the zone; only optional deletion of the stock spawn rows (out of scope by decision 4; the user may want a starter) | gap 2026-11-27 | waiting (scope call) | code |
| C-8 | **Client art in exports**: a build with Decor packs models copied from the user's install, so its `.eqg` is for the user's own client and server only; nothing marks or strips that on Export | gap 2026-11-27; umbrella decision 31 | waiting (policy call) | code |
| C-9 | **`.s3d` era output**: the default Classic–PoP look ships as `.s3d`/WLD in the real game, but we write only `.eqg` | gap 2026-11-27; north-star | waiting (wanted?) | code: `core/wld.py` is read-only |
| C-10 | Hand-renaming exported files to install over a different short name: whether client and server accept it | umbrella decision 15 follow-up | waiting (needs the client) | — |
| C-11 | Doorway-fit: catalogue RoF2 door models by theme and footprint and snap gated openings to one; today every door is `BBDOOR1` | ROADMAP "Design work captured" | open | code: `generators/sqlexport.py` |
| C-12 | **Client performance** not measured: frame rate, draw calls and triangle count of a decorated zone in the client | gap 2026-11-27 | open | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| No short-name concept; files named by an internal id (umbrella Known Limitation 9) | M1 wave 6 merge `17c1b94` (Build_Name), step 17 Export (master `be4d04e` close) |
| M6 SQL export (step 12 "out of this step") | step 17 |
| Doorway gates as doors at room openings (steps 11, 12) | step 17: one `doors` row per Gate (decision 36 A3); the door model catalogue stays open as C-11 |
