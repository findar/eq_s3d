# Design: zone-generator-winding-tunnels (roadmap step 23)

Written at master `b2db7b4`. Verify everything here against the code before working.

## Where a corridor's shape is decided today

| What | Where | Task |
|---|---|---|
| Route (straight, Z, L, U), legs, carry | `generators/routing.py` `plan_route`, `corridor_route` | 2 (adds `wind_leg`) |
| Footprint for conflicts | `routing.route_footprint`, used by `generators/layout.py` | unchanged |
| `cor.rough` | `generators/transitions.py` `draw_transitions`: `style.corridor_break` when plain | 2 sets the wind inputs |
| Leg mesh | `generators/geometry.py` `_emit_route` → `_add_leg` → `_add_rough_leg` (walls step in by up to `rough` × width; floor full width, straight) | 3 |
| Corridor RoomContext (decor grid) | `generators/room_context.py` `corridor_contexts`: pieces from route legs and bend squares | 4 |
| Map outline / EQ map | `generators/mapgeom.py` (from the built mesh's walls), `generators/outline.py` (rooms only) | 4 |
| Wall style rules | `rules/walls/rough.toml`, loaded by `generators/wall_styles.py` | 2 |

## Survey (task 1)

Extend `analyzer/wall_survey.py`, or add a sibling `analyzer/tunnel_survey.py`. Find tunnels in
stock caves: narrow floor runs between chambers in Blackburrow, Runnyeye, Crystal Caverns,
Solusek's Eye, Nagafen's Lair and Permafrost (the zones `rough.toml` was measured on). Measure
their centreline as a polyline: segment lengths, turn angles, wander as a share of span, and
width. The output feeds `[tunnel]` in `rough.toml`, for example `segment = [a, b]`,
`max_turn = deg`, `wander = share of span`. Read the WLD through `core/wld.py`, as the wall survey
does.

## The centreline (task 2)

`wind_leg(start, end, along_x, hw, clearance, rules, seed) -> List[(x, y)]`. Use a pure function
of its inputs, seeded from the corridor id and the leg index, never from a global stream. It must
not draw from the layout's rng (A4).

1. Run straight for `max(hw, rules.end)` from each end.
2. In between, take segments of length drawn from `segment`. Turn each segment by at most
   `max_turn`, steering back toward the axis as the wander nears `min(clearance - hw,
   wander × span)`.
3. End exactly on the far straight. The last turn closes the remaining offset; if that would
   pass `max_turn`, add segments.

**Clearance:** for each leg, the largest sideways distance on each side, in plan, before the strip
would meet another room's Box, another corridor's footprint, or this corridor's other legs. Take
the minimum along the leg. Rooms and corridors on other Levels count only when they overlap the
leg in Z (stacked Levels share a plan). Compute it once per corridor in `transitions.py`, where
`cor.rough` is set, and store it as `cor.wind = [w0, w1, ...]`: the per-leg wander limit, 0 for a
leg that stays straight. Add it to the corridor JSON only when it is non-zero. Old specs load with
`wind = []`.

## The mesh (task 3)

`_add_rough_leg` builds a straight leg today. Add `_add_winding_leg`:
- The floor is a strip of quads along the centreline, mitred at each turn, with z interpolated
  along the path.
- The walls on both edges keep the rough wobble (`rough` × width), measured from the strip's
  edges.
- The ceiling follows the strip.
- The ends match the square ends `_add_rough_leg` makes, so the bend squares and room openings
  weld exactly as today.

Collision is per triangle (lessons-learned "EQG collision"), so no BSP work is needed.

## Readers (task 4)

`room_context.corridor_contexts` rasterises each leg's floor from the same `wind_leg` call (the
same inputs, so the same polyline) and its walls from the mesh. `mapgeom` reads the built mesh, so
check its wall extraction on angled walls. The map SVG's corridor drawing (`generators/mapview.py`)
should follow the centreline if it draws legs as rectangles.

## Gate and bands (task 5)

Sweep cave and warren dungeons (graph layout, 8–30 rooms, each verticality) with
`scripts/sweep_themed_navigability.py`. Measure the fail share of at least 200 Draws per layout
with `scripts/quality_sweep.py`.
