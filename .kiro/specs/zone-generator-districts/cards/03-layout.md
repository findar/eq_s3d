# 3 — Districts in the layout

Index entry: `tasks.md` task 3. Requirements 3 and 7. Design "Shape", "Layout".

## Goal
`LayoutGenerator.generate(..., districts=False, district_plan=None, district_relationship="")`:
partition after the engine and before pacing (A4), pacing with per-District climaxes, labels per
District, Threshold flags on corridors, `spec.districts`, Threshold Gates first (23.7), the
crossing-split check (Req 3.3). Both layouts.

## Done when
- [ ] For dungeon seeds on classic and graph, 8–30 rooms, locks 0–3, Districts on: Districts as
      Req 1; exactly one climax per District and one entrance; Threshold corridors flagged and no
      other; Gates on Thresholds first with keys reachable; walkability and solvability gates
      pass. → verify: `python -m pytest tests/test_district_layout.py -q`
- [ ] How often the crossing split fails a districted Draw, over at least 200 Draws per layout,
      is in the commit body; above about 2%, the fallback in design "Layout" is used and recorded.
- [ ] Districts off, and Districts on below 8 rooms, give byte-identical specs to master: the
      byte check in `tasks.md` passes; `python -m pytest tests/ -q` is green.

## Pitfalls
`_apply_pacing` biases sizes once; don't call it twice. `_resolve_crossings` and
`_resolve_conflicts` mutate `edges`; run the District check after both. Lessons-learned
"Same-axis room pairs need a Z-route" and "Bound elevation by the corridor run" still apply to
the pruned graph. Look at a few districted maps (`generators/mapview.py`) before ticking.

## Result
