# Archive — zone-generator-wilderness, waves 1–4

Finished work, collapsed. Agents don't need to read this file to pick up a
task; it is here for the "why" behind decisions that later tasks build on.

The full original work log (every subtask, test count, timing and rationale) is
the pre-pilot `tasks.md`, preserved in git:

```
git show 917bae3:.kiro/specs/zone-generator-wilderness/tasks.md
```

## What landed

All four branches are merged into `master` (tip `917bae3`). Nothing below is
wired into the build yet: the wilderness package is called only by tests until
task 2 wires it into `TerrainBackend`.

| Wave | Branch | Tip | What it built | Proven by |
|------|--------|-----|---------------|-----------|
| 1 Matrix IR | `agent/wild-matrix` | `5e76b82` | `generators/wilderness/{matrix,biome_resolve}.py`: the Design_Matrix (typed 2D terrain cells), plains/Karana biome resolution in the rule planner, terrain-first `build_matrix` | Properties 1–6, 17 (`tests/test_wilderness_matrix.py`, `test_wilderness_biome.py`) — no geometry |
| 2 Graph_Replacement | `agent/wild-rewrite` | `0e97431` | `generators/wilderness/rewrite.py`: region graph + termination-bounded rewrite with apply-check-commit | Properties 7–9 (`tests/test_wilderness_rewrite.py`) — no geometry |
| 3 Noise + erosion + upsample | `agent/wild-synth` | `69a3843` | `generators/wilderness/synth.py` + `hydraulic_erosion` in `generators/field/terrain.py`: matrix-subordinate FBM, hydraulic + thermal erosion, Rim re-clamp, sharp-edge upsample | Properties 10–14 (`tests/test_wilderness_synth.py`) on the height array |
| 4 Bowl + built-mesh gate | `agent/wild-bowl` | `917bae3` | `generators/wilderness/bowl.py` (`assemble_bowl`, `build_bowl_ter`, `check_bowl`) + `OffMapBand` bowl-gate parameters in `analyzer/traverse.py` | Property 15 (`tests/test_wilderness_bowl.py`) on a real built TER, plus a negative guard that a breached rim is caught |

Suite at the wave-4 tip: **502 passed**, ~151 s (pytest-xdist).

## Decisions later tasks rely on

- **Matrix resolution:** `DEFAULT_ZONE_SIZE = 2400` u, `DEFAULT_CELL_SIZE = 150` u,
  giving a 16×16 matrix (`matrix.py`). This is the coarse end of the design band
  and is up for re-tuning in task 5 once someone has looked at it.
- **v1 rewrite rules:** exactly two, `cliff → graded approach` then
  `lava → graded approach`. Cliffs are resolved before lava. The commit gate is
  *monotone progress*: the Rim stays sealed and the stranded set strictly
  shrinks (`0c38abc`; the earlier all-or-nothing gate stalled on two separate
  blockers). No river rule ships; v1 rivers hug the boundary.
- **Erosion settings** (`terrain.py`/`synth.py`): `HYDRAULIC_ITERATIONS=3`,
  `HYDRAULIC_INCISION=18`, `FLOW_EXPONENT=0.5`, `THERMAL_ITERATIONS=20`,
  `THERMAL_TALUS=0.6`, TER resolution 40 u. Order: noise → hydraulic → thermal,
  with the Rim re-clamped after every pass.
- **Rim geometry:** `RIM_BAND_FRACTION = 0.12` (~140 u ridge per side) and
  `SETBACK_FRACTION = 0.06` (~70 u flat margin), so the central ~82% per side is
  open basin.
- **Additive proof:** the plain-terrain `build_terrain` height checksum for seed
  1337 is `sha256:2af33e68…74b6dec` and did not change. The hydraulic pass runs
  only on the wilderness synthesis path.
- **How each Rim edge type is sealed:** a mountain edge is sealed by slope (rim
  faces are too steep to stand on). A river edge is sealed by an
  Invisible_Wall `RegionSpec` (generic → `APV`) plus visual-only water. A
  zoneline edge is a flat `RegionSpec(kind="zoneline")` → `ATP`, the one
  deliberate opening. Interior lava is spiked +60 u and marked
  `RegionSpec(kind="lava")` → `ALV`, flagged damaging. Edge and barrier
  metadata is collected on `BowlResult.edges` / `.barriers`, but is not yet
  written to the sidecar (task 8).
- **How off-map exits are detected:** each one is an `OffMapBand`, an XY
  rectangle just outside a Rim segment. A leak means a face reachable from
  Spawn has its centroid inside a band. This reuses `build_walk_surface` and
  `flood_reachable` unchanged.
- **Timing budget:** a full build (matrix → rewrite → synth → bowl → gate) has a
  median of ~0.26 s, far under the 5-minute budget.

## Old task → new task

| Old | Now |
|-----|-----|
| 1–7, 9–10 (all subtasks), 8.1, 8.3, 11.1 | done — this file |
| 8.2, 11.2 (human 3D passes) | task 4. They could never run, because nothing rendered before the backend wiring |
| 11.3 (wave-4 note) | superseded. The integration note now comes from `scripts/task_status.py --note` |
| 12.2, 12.5, 13.1 | task 2 |
| 12.4 | task 6 |
| 12.3 | task 7 |
| 12.6, 12.7 | task 8 |
| 12.8, 12.9, 14.1, 15.1, 15.2 | task 9 |
| 14.2, 15.3 | task 10 |
| 13.2, 14.3, 15.4 | task 11 |
