# 2 — The winding centreline and its clearance

Index entry: `tasks.md` task 2. Requirement 2. Design "The centreline".

## Goal
- `routing.wind_leg` gives a plain leg's winding centreline.
- `transitions.py` measures each rough corridor's per-leg clearance into `CorridorSpec.wind`.
- `[tunnel]` in `rough.toml` holds task 1's values, loaded and checked by `wall_styles.py`.

## Done when
- [ ] Property tests show that `wind_leg`:
      - is deterministic;
      - keeps every turn ≤ `max_turn`;
      - runs straight for at least `max(hw, end)` at each end;
      - keeps the strip (centreline ± hw) inside the clearance;
      - with zero clearance, returns the straight leg.

      → verify: `python -m pytest tests/test_winding.py -q`
- [ ] Over 10 cave dungeons (graph layout), most rough corridor legs get `wind > 0`, and no
      strip comes within the player's half-width of another room's Box or another corridor's
      footprint; counts are in the commit body. Same command.
- [ ] Specs without `wind` load, and the corridor JSON gets `wind` only when it is non-zero.
- [ ] The byte check passes with no golden moved. Nothing builds from `wind` yet, but sidecars
      record it: a moved golden is named.

## Pitfalls
- Never draw from a shared rng stream; seed from the corridor id and the leg index.
- Stacked Levels share a plan, so count only rooms and corridors that overlap the leg in Z.

## Result
