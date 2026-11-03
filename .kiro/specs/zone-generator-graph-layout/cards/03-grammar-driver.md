# 3 — Topology graph and rewrite driver

Index entry: `tasks.md` task 3. Requirements 3. Design "Topology_Grammar".

## Goal
`generators/topology/`: `TopologyGraph` (tagged nodes, undirected edges, shape stats) and the apply-check-commit driver with the invariants and step cap. Rules are a protocol here; task 4 writes the real ones.

## Done when
- [ ] `TopologyGraph` measures dead-end share, cycle rank and deep-end distance (the survey's definitions).
- [ ] The driver grows a graph to exactly n rooms (1–30) with test rules, rejects any application that breaks connectivity, degree ≤ 4 or loop length 3–5, and raises `TopologyError` at the cap.
- [ ] Hypothesis properties G2 and G3 (design table) over seeds and n.
      → verify: `python -m pytest tests/test_topology_grammar.py -q`

## Pitfalls
- Deterministic: candidate sites in sorted order before the rng picks one; no set iteration order leaks into choices.
- Don't import or generalise `generators/wilderness/rewrite.py` (design: not shared).

## Result
