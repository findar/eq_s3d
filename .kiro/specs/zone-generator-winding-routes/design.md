# Design — winding routes (step 25)

## Data

`CorridorSpec.path: List[Tuple[float, float]]`, default `[]`, written by `_corridor_dict` only
when set (as `wind` is). When set it is the corridor's whole centreline, opening to opening, and
`wind` is `[]`.

## The route line (`routing.wind_route`)

Inputs: the route's waypoints (straight, Z, L, U), `hw`, the `TunnelRules`, a seed
(`wind:<id>:route:<from xy>`). Steps:
1. Run-outs: from each opening a straight run of `max(hw, rules.end)` along its exit axis.
2. Bend cuts: each 90° bend of the rest of the route becomes a chamfer of `ceil(90 / max_turn)`
   turns (two 45° turns at `max_turn` 60), cut back from the corner by the most that keeps both
   neighbouring runs at least `segment[0]` long.
3. Wander: each straight run between cuts longer than `2 × segment[0]` is split and offset
   sideways as `wind_leg` does, capped by `wander × span`.

The line starts and ends exactly at the openings' points.

## Clearance (`transitions.measure_winds`)

For a rough plain corridor (no steps, no bridge, no Transition line), build the strip polygon of
`wind_route`'s line (mitred, as `_add_winding_leg` would) and test it against every room box and
every other corridor's `_corridor_boxes` that overlap its Z band (± `WIND_Z_SPARE`): the strip
keeps `PLAYER_HALF_WIDTH` from each box in XY, except the two rooms it joins, which it may enter
only along its run-outs. Pass: `path = line`, `wind = []`. Fail: step 23's per-leg `wind`.

## Mesh

`_emit_route` with `cor.path`: one strip as `_add_winding_leg` builds it, from `from_z` to `to_z`,
flat over both run-outs, the rise spread evenly over the rest by length (its grade is at most the
route's own carry leg's, since the path is longer). Openings as today.

## Readers

`room_context._strip_plan`, `mapview.corridor_path`, `mapgeom` (angled wall lines fold already)
and `traverse.corridor_continuity` take the path's segment rects as they take a winding leg's.

## Run length

`layout.PROFILE_RUN_FACTOR["cave"]` (9 since step 23) is re-measured: the share of cave rough
corridors with a `path` or a winding leg, and the door-to-door length, at factors 3–9.
