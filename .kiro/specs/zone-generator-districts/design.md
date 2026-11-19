# Design — zone-generator-districts (roadmap step 20)

Written at master `a26d07b`. Verify against the code before working. The umbrella design's
"Districts", "`DistrictSpec`" and "District partition" sections are the starting point, amended
by `requirements.md` A1–A6.

## Shape

```
engine.generate -> rooms, edges, entry
   zone entrance (pacing's rule, no rng)
   k = district_count(n, plan.districts)                 # 1 when off (A1) or n < 8
   part = partition_districts(rooms, edges, entrance, k, rng)   # k == 1: no rng, edges unchanged
   edges = part.edges; room.district = part.assign[i]
   _apply_pacing(rooms, edges, entry, climaxes=per-District climaxes)   # once (A4)
   label_rooms(..., districts=assign_district_purposes(part, plan, rng))
   ... separate, elevation, crossings (Req 3.3 check), corridors (threshold flags), gating (Thresholds first)
   realize_semantics: per-District palette and light; Threshold ends differ (23.5)
```

## Partition (`generators/districts.py`, task 1)

The umbrella's tree cut, unchanged: BFS tree from the entrance with adjacency sorted by index
(as `layout.gate_tree`), `k − 1` cuts each leaving at least `min_size` rooms on both sides,
scored by distance from n/k with a bonus when the parent is a hub, ties by `rng.random()`. Rooms
take the District of their deepest cut ancestor; District ids are 0 for the entrance's and then
by cut depth. Kept edges: tree edges, plus any edge whose two ends share a District. The cut
edges are the Thresholds.

```python
@dataclass
class Partition:
    k: int; requested: int
    assign: list[int]                 # room index -> District id
    edges: list[tuple[int, int]]      # pruned
    thresholds: list[tuple[int, int]] # (parent side, child side)
def district_count(n: int, on: bool) -> int
def partition_districts(rooms, edges, entrance, k, rng) -> Partition
def district_climaxes(part, edges, entrance) -> list[int]   # one per District (23.4)
```

`DistrictSpec` as the umbrella (id, purpose, entrance_room, climax_room, room_ids,
threshold_corridor, relationship, palette, light_mood), on `ZoneSpec.districts` (empty for one
District). `CorridorSpec.threshold: bool = False`. Both default on load (umbrella 11.5).

Pacing with Districts: `_apply_pacing` gains `climaxes: list[int] | None`. When given, those rooms
are the climaxes (one per District: deepest by in-District BFS from the District entrance, ties
to the lowest index) and the single-climax rule is skipped. Depth stays BFS from the zone
entrance over the pruned graph. With k = 1 the argument is None and pacing is as today.

## Purposes (`districts.assign_district_purposes`, `semantics`, task 2)

Compatibility table as data in `districts.py`: for each Purpose, the Purposes it may sit next to
(`sequential`) and the ones it contrasts with (`factional`). The table is the lead's first cut;
the first look judges it. Choice with no proposals: `sequential` walks a compatible chain from a
first Purpose (the plan's if set, else drawn); `factional` draws pairwise-distinct contrasting
Purposes; `abandoned_vs_active` gives every District the first Purpose. Proposals fill Districts
in id order; unknown values fall back with a note.

`label_rooms(..., districts=None)`: with Districts, a room's arc is its District's Purpose and its
depth is in-District depth; `room_theme` is the District's Purpose; `spec.dungeon_theme` stays the
zone's (District 0's). `realize_semantics` picks the palette by the room's `room_theme`, with an
`abandoned` variant (saturation and light scaled down, a distinct Material_Name). At each
Threshold, if the two ends would share a material set and light, the child side takes the variant
(23.5, 23.10).

Palettes added for `war_city`, `warren`, `corrupted_sanctum`, `mine_delve` (A3). **They apply
only to rooms in a multi-District zone**, so one-District zones stay byte-identical (Req 7;
archive decision 4).

## Layout (`generators/layout.py`, task 3)

As the Shape above. Gating: Threshold corridors are tried first, shallow to deep, keys on the
parent side (`gate_key_room` with the near set), then the existing tree-edge order. A Threshold is
a bridge of the pruned graph, so it is in every spanning tree and its far side is exactly the child
District plus Districts beyond it.

Crossing splits (`_resolve_crossings`) add a waypoint room C on edge A–B. After the crossing and
conflict passes, check: every edge joins one District, or is a Threshold. A split that breaks this
raises `ValueError("district threshold split")`, which the pipeline counts as a plan error and
redraws. Task 3 measures how often (seed sweep in the commit body); if more than about 2% of
districted Draws, assign C to A's District instead and say so in `archive.md`.

## Plan, prompt and Server (tasks 4, 5)

`ZonePlan.districts: bool = False`, `district_plan: list[dict]` (≤ 3, `{purpose}`),
`district_relationship: str = ""`. `plan_to_spec` passes them to `LayoutGenerator.generate`
(dungeon only, A2; else a note). Rule planner: a bundled phrase table ("living and dead",
"two factions", "upper and lower", "fallen to", "overrun by", …) maps to a count, the Purposes it
names (archetype words already matched by `_match_archetype`) and a relationship. Sidecar:
`districts` list (umbrella 27.3); rooms already carry `district`; corridors gain `threshold`.
CLI `--districts`; the Server's generate takes the three fields like the other plan fields, and
the note goes to `warnings`.

## Quality (task 6)

`spec_key` and `BAND_TABLE` gain the resolved District count (1 for every existing row, so those
don't move). The sweep's `--districts` measures k = 2 and 3 dungeons on both layouts; rows filled
by step 19 decision 4's rule; `district_balance` bounded on its low side.

## Page and map (task 7)

Controls: a Districts checkbox (dungeon only), sent as `districts`; a sidecar plan with Districts on
ticks it. Map (`mapview.render_map_svg`): a convex hull per District, a light fill per District id,
drawn after the outline and before the room shapes; Threshold corridors drawn heavier. The legend
lists the Districts with their Purposes. Room panel: "District 1 — tomb".

## Risks

- Byte identity with the switch off is the hard line (Req 7): every new rng draw sits behind
  k ≥ 2.
- The partition can fail its sizes on a stringy graph; k drops with a note rather than an error.
- Graph rule sets that already make wings may get cut across their wings (A5); the first look
  judges whether to honour their labels later.
