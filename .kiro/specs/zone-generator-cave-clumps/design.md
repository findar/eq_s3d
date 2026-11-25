# Design — zone-generator-cave-clumps (roadmap step 29)

## Draw time (Req 1)

`start_positions` tries up to 64 starts; each placed room calls `_start_crossings` against
every placed edge, recomputing corridor rectangles. Keep the placements identical and make the
work incremental: cache each placed edge's rectangles once (`_Placed` already holds arrays),
test only edges whose bounding box meets the candidate's, and stop counting at the best score
so far. `_untangle` re-scores every edge each round; re-score only edges touching a moved room.
Any change that alters a placement is out of scope (Req 1 asks for equality).

## Throats (Req 2)

A throat is an ordinary corridor edge whose spacing is drawn near zero, so no IR change is
needed: `CorridorSpec` stays, the rooms sit one wall thickness plus at most one corridor width
apart, and the door cuts on facing walls line up. A share of cave edges (`THROAT_SHARE`, about
0.3, drawn from the same salted `edge_jitter` hash so a seed keeps its throats) take a
throat spacing; a throat holds its bearing near the wall normal so the opening is not cut at a
steep angle through a short run. Stairs, Bridges and Level changes never take a throat.

Task 2 probes the shortest corridor every reader accepts before task 3 picks the throat's
length: build caves with forced short spacings and see where mesh flush, outline, gate,
decor contexts and map first fail.

## Clumps (Req 3)

`BEARING_CLUMP` already rests 0.3 of edges at 0.27 runs, but the springs and `BEARING_REPEL_RUNS`
push unjoined rooms back apart. Throats bring joined pairs together; clumping also needs
unjoined neighbours of a throat pair to sit close: lower the repel for rooms sharing a throat
neighbour, or let the springs hold throat edges rigid. Task 3 measures with
`python scripts/grid_score.py --shapes --kinds cave`.

## Measuring

`scripts/grid_score.py --shapes` gains the share of throat edges (door-to-door ≤ one corridor
width), read the way `stock_room_shapes.py` reads "direct".
