# Design — winding control (step 26)

## Data

- `ai/schema.py`: `ZonePlan.winding: float = 1.0` and the constant `WINDING_MAX` (provisionally
  2.0; task 2 measures and may change it). Validation clamps the value to `[0, WINDING_MAX]`, and
  a non-number falls back to 1.0.
- `generators/zone_spec.py`: `ZoneSpec.winding: float = 1.0`, written to JSON only when it is not
  1.0 (A4 bytes), and read back with a default of 1.0.
- The plan reaches the layout the way `verticality` does (follow it through
  `generators/pipeline.py` / `builder.py` to `LayoutEngine`). The engine records it on the spec.

## Scaled rules

One helper gives the scaled tunnel for a spec, for example
`wall_styles.tunnel_rules_for(spec)` or `TunnelRules.scaled(k)`:
`TunnelRules(segment, max_turn, wander * k, end)`.

- At k = 1 it returns the same object, so nothing changes.
- `measure_winds` / `measure_routes` (transitions.py) take it.
- **Every caller of `routing.winding_legs` with `rules=None` must get the spec's scaled rules.**
  `_wind_limit` clips the stored `wind` limit at `rules.wander × span`, so a reader with the base
  rules would clip a k > 1 leg and disagree with the mesh.

  Grep `tunnel_rules()` and `winding_legs(` across `generators/`, `analyzer/` and `scripts/`. The
  callers are the mesh, `room_context`, `mapview` / EQ map, and `traverse.corridor_continuity`.
- At k = 0, `measure_winds` and `measure_routes` give `wind = []` / `path = []` for every
  corridor, and skip the work.

## Range (task 2)

wander × k is capped by clearance (`min(clearance, wander × span)`), so large k only pays off
where there is room.

Task 2 sweeps k over {0, 0.5, 1, 1.5, 2, 3} on 40 cave graph builds and 20 warren graph builds
(seeds 1000–1039 and 1000–1019, 8–30 rooms, each verticality, `EQ_PATH` set). For each k it
records:

- the share of rough corridors that wind (path or leg);
- the median and p90 of the largest sideways stray per corridor;
- the door-to-door median;
- gate passes.

`WINDING_MAX` is the largest k whose stray keeps rising and whose gate holds. If k > 1 gives
little more stray because the cave run (4 widths) leaves no room, task 2 may tie the cave run
factor to k (for example `4 + c × (k − 1)` above 1). It records the measured choice in
`archive.md`. At k ≤ 1 the run factor stays 4, so k = 1 stays byte-identical.

## Controls and words (task 3)

- **Server:** the generate request's plan carries `winding`, validated by the schema.
- **Web:** a range input `#winding` (0 to `WINDING_MAX`, step 0.25, default 1) with its value
  shown. It appears for dungeon, city and outdoor_dungeon (`usesControl`). It is sent only when
  shown, appears in the summary line, and suppresses WASD while focused (lessons-learned "Web
  viewer").
- **Rule planner:** straight words → 0.25, twisting words → 1.75 (or `WINDING_MAX`'s middle), no
  words → 1.0. An explicit Controls value wins over the words, as with verticality.
- **LLM planner:** the field is in its schema text.
