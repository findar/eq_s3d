# Design — zone-generator-quality (roadmap step 19)

Written at master `19c041d`. Verify against the code before working; the umbrella's
"Quality and conformance" section and its metric table are the starting point, amended by
`requirements.md` A1–A4.

## Shape

```
spec_factory(seed) --Draw--> ZoneSpec --measure--> QualityReport
        ^                                   | fail, unpinned, < 32 Draws, time left
        +-----------------------------------+
best Draw --> build --> hard gates --> finalize (sidecar quality = quality_summary(report))
```

The meter never builds. The pipeline owns the loop and the `degraded` / `reason` fields; the meter
only measures (umbrella 24.8).

## Meter (`generators/quality.py`)

```python
@dataclass
class OutOfBand: metric: str; value: float; lo: float | None; hi: float | None
@dataclass
class QualityReport:
    metrics: dict[str, float]; out_of_band: list[OutOfBand]
    passed: bool; score: float; degraded: bool = False; reason: str = ""
Band = tuple[float | None, float | None]       # inclusive; None = unbounded side
def measure(spec, bands=None) -> QualityReport   # bands None -> bands_for(spec's key)
def bands_for(zone_type, layout, n_rooms, verticality) -> dict[str, Band]
def quality_summary(report) -> dict              # the Quality_Block
def spec_key(spec) -> tuple                      # (zone_type, layout, n_rooms, verticality)
```

- Graph: rooms as nodes; a corridor is an edge when both `from_room` and `to_room` name rooms
  (stubs and Mouth tunnels aren't). Parallel corridors between one pair count once.
- `critical_path_ratio`: the climax is the room with role `climax` (else the deepest
  `graph_depth`); its `graph_depth` / (N − 1).
- `size_cv`: floor area is the Outline's area when the room has one, else width × depth.
- `elevation_levels`: distinct `round(floor_z / 8)`.
- Score: Σ over failing metrics of distance / max(1, band width or |bound| when half-open).
- Metrics are rounded to 6 places so a JSON round-trip measures the same.
- `layout` and `verticality` come from the spec's own fields (check `ZoneSpec` for where the
  layout engine and verticality are recorded; if they aren't, read them from the plan the
  pipeline holds and pass the key in).

## Bands (task 2)

`scripts/quality_sweep.py` draws specs (no builds) for zone type × layout × verticality × room
counts, writes a CSV of metrics and Draw times, and prints per-key quantiles. Task 2 picks the
bands (start from the umbrella table; widen where ordinary output fails), puts them in
`quality.py` as a table, and records the share redrawn and the expected Draws per key in
`archive.md`. A key with too few rooms or no sensible band stays unbounded.

## Pipeline (`generators/pipeline.py`)

- Before the gated loop's first attempt (and on each later STAGE_ZONE attempt only while the
  quality loop hasn't finished), an unpinned seed runs `_quality_draw`: Draw, measure, keep the
  best; stop on a pass, at 32 Draws, or when the timeout is used up. The chosen spec is built as
  that attempt. Rooms-stage rerolls (`rooms_seed`) draw the same way when the factory takes
  `rooms_seed`.
- After the quality loop is done, a hard-gate failure retries as today with no quality Draws.
- `finalize` writes `quality` into the sidecar from the report it is given; `ValidatedBuild`
  gains `quality`. Ungated builds measure and record too.
- `stages` (partial rebuilds) and edits: measure only (A4). The edit path sets
  `edit_outside_bands`; a decor rebuild of a degraded parent keeps the parent's reason.
- `PLAN_ERRORS` during a quality Draw count as a failed Draw (score infinity), not an attempt.

## Route, CLI, listing

`server/app.py`: every build-bearing response adds `quality` (the sidecar entry) and the reason
to `warnings`; the versions listing entry adds `quality: {degraded, reason}` (null when the
sidecar has none). `main.py` prints the 25.9 lines.

## Page (`web/src/quality.ts`)

A banner element over the viewport (`role="status"`, no close control) and an indicator in the
side panel's Version row; a Quality list in the metrics area. Fed from the open version's sidecar
`quality` (the page already loads the sidecar per version), so generate, rebuild, edit and the
version steppers all go through one function. No sidecar entry: "quality unknown", no list.
