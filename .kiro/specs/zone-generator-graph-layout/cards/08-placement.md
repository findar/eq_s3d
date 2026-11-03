# 8 — Placement, size classes and the graph engine

Index entry: `tasks.md` task 8. Requirements 6. Design "Size classes", "Placement", "Vertical relations".

## Goal
`embed.py`: size classes to footprints and heights, the Placement registry with `spring`, and the `may_overlap_in_plan` predicate (always False). `GraphEngine` in `layout_engine.py` (rule set → graph → placement → `EngineResult`). In `layout.py`, the role size bias skipped for engines that size rooms, and elevation reading edge relations.

## Done when
- [ ] G7: rooms take their class's size; grown layouts never overlap in plan, keep the classic corridor clearance; the `entrance` node is the entrance room; the final graph (after Job B) is connected; over seeds, n and both sets.
- [ ] G8: Edge_Fidelity measured over the sweep seeds; the bar (≥ 0.85) and the measured mean are in the commit body and the test.
- [ ] G9: `above` / `below` / `level` hold after elevation unless the loop relax broke them, which is counted.
- [ ] G10: with a synthetic Envelope (as in `tests/test_envelope.py`), grown rooms fit as classic ones do. G11: umbrella Req 21 holds.
      → verify: `python -m pytest tests/test_topology_embed.py tests/test_layout_engine.py -q`

## Pitfalls
- Measure fidelity after Job B (`LayoutGenerator.generate` with the graph engine), not after placement alone: Job B's crossing splits and conflict drops are what lose edges.
- lessons-learned: same-axis room pairs route as Z-corridors. Place neighbours on a free side; don't fight the router.
- Don't re-tag roles after layout: the entry point goes through `_apply_pacing`'s `entry` argument.
- The task 2 goldens must still pass: classic is untouched.

## Result
