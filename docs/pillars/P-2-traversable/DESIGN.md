# P-B Traversable — design (living)

How walkability is made and proven now. Checked against the code at `c3d9b99`.

## The agent

`analyzer/traverse.py` `AgentModel`: 1 u ≈ 1 foot, a player about 6 u tall, Z up. A triangle is
standable when its slope is under 40°. Two standable triangles connect when they truly touch
(shared geometry or touching footprints) at matching floor height, within the 3 u step-up. EQ
collision is per triangle (lessons-learned), so a walk over the mesh is faithful to the client.

## What the gate checks

`validate(eqg, spec, check_corridors=True, placed=...)` builds a walk surface from the TER and
floods it from the safe point.

| Check | Function | Fails when |
|---|---|---|
| Walk surface | `build_walk_surface` | (built once) only floor-wound faces count, so a ceiling never reads as floor |
| Room reach | the flood | a room's floor footprint isn't reached from the safe point |
| Way back | `find_drops` + a reverse flood | a room is reached only by a one-way drop with no way back (strong connectivity) |
| Corridors | continuity and conflicts | a corridor's floor has a gap, or two corridors clash |
| Outlines | `check_outline` | a shaped room's floor is walled off or a Throat (the floor a door needs) is narrow |
| Features | `check_features` | a pillar, boulder or dais walls part of the room off |
| Transitions | `check_transition` | a Seam, Frame or Breach leaves under 2 H of headroom or a narrow way |
| Connectors | `check_connector` | a stair or Bridge isn't climbable or is walled through a room |
| Placed models | `analyzer/footprints.py` | a Prop, Structure or tree cuts the way (`footprint_cut`) or an Enterable opening is under 8 u wide or high |

Landscapes (`wilderness`, `outdoor_dungeon`) also run the **bowl gate**: no fall out of the
world, the Spawn reaches the playable ground, every outdoor-dungeon room is reached from the
outdoor Spawn.

## In the pipeline

`generators/pipeline.py` `generate_validated`:

- Each attempt builds into `output/.attempts/<zone>/a<k>/`. Pass ⇔ rooms reached ∧ corridors
  pass ∧ format check passes. A pass moves into `v<n>/`; a fail is logged to
  `output/validation_failures.jsonl` and removed, so a rejected attempt leaves nothing behind.
- **Blame**: on a random seed the pipeline rerolls only the stage it blames, Decor (new
  `decor_seed`) or rooms (new `rooms_seed`), at most twice per World (`MAX_STAGE_REROLLS`), then a
  fresh `seed`. A pinned seed that fails raises `GenerationFailed`; it is never swapped.
- **Budget**: at most 8 attempts (`DEFAULT_MAX_ATTEMPTS`), a per-type timeout (20 s room types,
  60 s wilderness), and an overall 240 s budget (`DEFAULT_BUDGET_S`).
- **Partial gate**: a decor rebuild re-checks only what changed against the parent's kept
  result (`shell_report`) and must agree with the full gate.

## Making geometry walkable

- **Routing** (`generators/routing.py`, `geometry.add_corridor` → `_emit_route`): straight for
  collinear openings, a Z-corridor (three legs) for parallel walls, an L only for a true
  cross-axis pair. The whole rise sits on one leg, so both openings land flush.
- **Grade cap**: room heights come from a BFS over the room graph, each step capped at
  `run × 0.5` (about 26.6°); `_relax_elevation` then pulls every room into the walkable band of
  all its neighbours, loop edges included.
- **Ramps** are split into segments rising at most 2.5 u (`MAX_SEG_RISE`), because the agent
  compares triangle heights; a single-quad ramp reads as a cliff.
- **Stairs** (`StairPlan`): a straight flight or a Switchback (two half-rise flights and one
  landing), risers at most 2 u. **Bridges** cross a lower room through a shaft in its ceiling.
- **Winding**: a rough corridor's centreline winds only into clearance measured from the
  finished spec (`CorridorSpec.path`), keeping a player's half-width from every room and corridor
  that overlaps it in Z.
- **Drops**: 1 in 10 links between Districts may be a one-way drop of 6–80 u; never the only way
  back.

## Known gaps in the model

- No general headroom check over a standable face (only Transitions and Enterable openings).
- The seam rule joins floors within 2 u in XY and 3 u in Z with no wall test.
- A solid Feature's hollow can read as floor (decor works round it).
- `corridor_conflicts` measures a corridor's straight route, not its winding path.

See [OPEN.md](OPEN.md).
