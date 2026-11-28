# P-D True-layout artifacts — open items

Status and Checked as in [P-A's OPEN](../P-A-web-app/OPEN.md). Roll-up: [OPEN.md](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| D-1 | The map's "return" marks are inferred (`drop_returns` isn't saved in the spec) | step 31 archive | in flight (step 32 task 3) | — |
| D-2 | A wrapping District's hull overlaps its neighbour; a District label can sit under the legend | steps 20, 31 archives | open | record |
| D-3 | A map whose outline trace fails gets no layers | step 31 archive | open | record |
| D-4 | A box build with an extra depth band: 30-room dungeon seed 403, moderate, 4 bands on 3 Levels (`test_elevated_box_builds_have_one_band`; dungeon layout, pre-existing) | step 13 archive | open | record |
| D-5 | The in-client map window has never shown one of our `.txt` files | umbrella decision 21c | waiting (see C-1) | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| The map is a spec schematic, not the real walls (umbrella Known Limitation 8) | step 1b, master `a97231a` |
| Map outline depends on face order (`test_canonical_outline`, steps 9 and 10) | `0af5124` |
| The page's Socket markers infer the map's world-to-pixel mapping from room labels (step 12) | `bd394c6` (step 13 task 9: the SVG carries its frame) |
