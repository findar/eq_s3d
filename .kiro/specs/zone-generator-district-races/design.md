# Design — zone-generator-district-races (roadmap step 31)

Written at master `070126c`. Verify against the code before each task: it moves.

## Order

The one-way gate (task 2) lands before anything can make a drop, so every later task is judged
by it. Race and hall length per District (tasks 4, 5) change sizes only. Intrusion (task 6)
adds links; drops and loops (task 7) change how links meet floors; boundary decor (task 8) is
dressing. Controls (task 9) come last so the words drive finished behaviour.

## Measuring (task 1)

- **Hall length by race:** `scripts/stock_room_shapes.py --halls` (step 30) per zone, grouped
  by a hand table of stock zone -> inhabiting race (e.g. Kael giants, Sebilis frogloks, Chardok
  sarnaks, Runnyeye/Droga/Nurga goblins), in H of that race. A race "has a signal" if its
  zone-median p50 differs from all-built by more than the zone-to-zone spread.
- **Drops:** run the traversal agent's floor graph over stock meshes with a step-down limit
  raised: a floor edge whose neighbour floor is more than 3 u below (and no wall between) is a
  drop; report heights and the share of passage ends that drop. `MAX_DROP` is the stock p90,
  rounded; the flush weight is 1 minus stock's drop share at District-like boundaries if
  measurable, else the lead decides.
- **Layered links:** in stock zones mixing built and cave parts (step 8 listed some), count the
  links between the parts.

## The one-way gate (task 2)

`analyzer/traverse.py` keeps its two-way seam test and adds a directed pass: candidate pairs
that fail `max_step_up` but sit within `MAX_DROP` below, with the upper face's edge open (no
wall face between), become a directed edge upper -> lower. Reachability becomes two floods:
from the entrance forward, and from the entrance over reversed edges; both must reach every
room. With no directed edge the result equals today's (an undirected component check), so
reports are identical: proved by re-running step 28's report comparison over the sweep.

## Race and hall length per District (tasks 4, 5)

`DistrictSpec.race` (written only when set). `LayoutGenerator` sizes rooms per District
(`semantics.room_side(race, t)` with the District's race), corridors by their District, and a
cross-District corridor by the smaller H. The Graph placement's run becomes per edge: `spring`
takes an optional per-edge run map (`run x district_hall(d)`; cross edges the mean). The
partition already happens before placement (`layout.py` ~922), so each edge's District is known.

## Intrusion, drops and loops (tasks 6, 7)

`RELATIONSHIPS` gains `intrusion`. For an intrusion pair `partition_districts` keeps up to
N cross edges (task 1's count) instead of one; the extra ones get `CorridorSpec.transition`
form `breach`, rough. A drop is `CorridorSpec.drop` (u, written only when set): the corridor
runs flush from its upper room and enters the lower room's wall `drop` u above that room's
floor; the wall below the opening stays. Choosing drops: per cross link, flush unless a
salted draw under the drop share picks a drop AND the directed graph stays strongly connected;
for an intruder entered only by drops, the planner adds a flush return link from the room
farthest from the landing (requirement 8). Gating and `solvable` read drops as one-way.

## Boundary decor (task 8)

A host room entered by a breach draws a share of its decor layers from the intruder Purpose's
decor (`generators/decor/`), keeping the host's walls (step 22's per-District look picks walls
and decor per room already; this splits them).

## Controls and words (task 9)

Controls: per-District race selects next to the District Purposes, `intrusion` in the
relationship select. Rule planner: phrases naming two races or a tunnelling/burrowing verb set
a host and an intruder District. LLM schema and server pass-through as step 30 task 3.
