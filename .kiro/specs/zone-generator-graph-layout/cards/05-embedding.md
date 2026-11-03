# 5 — Embedding and the grown engine

Index entry: `tasks.md` task 5. Requirements 5. Design "Embedding".

## Goal
`generators/topology/embed.py` places a Topology_Graph's rooms in the plane; `GrownEngine(profile)` in `generators/layout_engine.py` runs grammar then embedding and returns `(rooms, edges)`.

## Done when
- [ ] G5: grown layouts never overlap, keep the classic corridor clearance, and the final graph (after Job B) is connected, over seeds, n and profiles.
- [ ] G6: Edge_Fidelity measured over the sweep seeds; the bar (≥ 0.85) and the measured mean are in the commit body and the test.
- [ ] G7: with a synthetic Envelope (as in `tests/test_envelope.py`), grown rooms fit as classic ones do.
- [ ] G8: umbrella Req 21 holds on grown layouts.
      → verify: `python -m pytest tests/test_topology_embed.py tests/test_layout_engine.py -q`

## Pitfalls
- Measure fidelity after Job B (`LayoutGenerator.generate` with the grown engine), not after embedding alone: Job B's crossing splits and conflict drops are what lose edges.
- lessons-learned: same-axis room pairs route as Z-corridors. Place neighbours on a free side; don't fight the router.
- The classic goldens from task 2 must still pass: registering the engine changes nothing for classic.

## Result
