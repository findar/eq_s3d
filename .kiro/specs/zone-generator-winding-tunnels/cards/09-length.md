# 9 — Cave tunnels as long as stock

Index entry: `tasks.md` task 9. Added by the lead at the task 2 merge (archive decision 5).

## Goal
Task 2 found that a cave's corridor legs are too short to wind: median 21 u, p90 60 u, while a
turn needs about 80 u. The graph layout rests an edge at `RUN_FACTOR` (2) corridor widths, so
rooms stand close. Stock tunnels are long.

- Measure the stock tunnels' span (centreline length) with `scripts/tunnel_survey.py`.
- Give the cave profile its own run: `LayoutContext.run_factor`, None for the default, set from
  the profile like `height_shift`. Cave corridors then come out near stock tunnel lengths.
- Every other zone's layout is unchanged (A4).

## Done when
- [ ] The survey prints the tunnel span's p10/p50/p90, and the chosen cave run factor is written
      in the commit body.
- [ ] Over 10 cave dungeons (graph layout, 12 and 25 rooms):
      - the median plain rough leg is within the stock span's p25–p75;
      - most plain rough legs get `wind > 0`;
      - no strip comes within the player's half-width of another room's Box or another
        corridor's footprint;
      - the counts are in the commit body.

      → verify: `python -m pytest tests/test_winding.py tests/test_cave_profile.py -q`
- [ ] Card 02's unticked check is ticked with "(met by task 9)", and its Result filled in.
- [ ] The byte check passes with no golden moved; `python -m pytest tests/ -q -m "not slow"` is
      green.

## Pitfalls
- `generators/layout.py` and `layout_engine.py` are hotspots: touch only the profile's run.
- Longer runs push rooms apart. Check that 30-room caves still fit and still pass the gate
  (`tests/test_cave_purpose.py`, the walkability tests).

## Result
