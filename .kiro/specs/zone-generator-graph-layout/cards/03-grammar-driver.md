# 3 — Topology graph and rewrite driver

Index entry: `tasks.md` task 3. Requirements 3. Design "Topology_Grammar".

## Goal
`generators/topology/`: `TopologyGraph` (labelled nodes, undirected edges, shape measures), the `Rule` declaration, the pattern matcher with reattachment, and the driver (match, check, pick, apply, repeat until no placeholder) with the invariants, the room budget and the step cap. Task 4 writes the real rules; this task tests with small ones.

## Done when
- [ ] `TopologyGraph` measures dead-end share, cycle rank and deep-end distance (the survey's definitions).
- [ ] The matcher finds every placement of 1–3 node patterns (labels and edges) and reattaches outside connections as the rule says.
- [ ] The driver grows a graph to exactly n rooms (1–30) with test rules and no placeholder left, rejects any application that breaks connectivity, degree ≤ 4, loop length 3–5 or the room budget, and raises `TopologyError` at the cap.
- [ ] Hypothesis properties G2 and G3 (design table) over seeds and n.
      → verify: `python -m pytest tests/test_topology_grammar.py -q`

## Pitfalls
- Deterministic: candidate sites in sorted order before the rng picks one; no set iteration order leaks into choices.
- Don't import or generalise `generators/wilderness/rewrite.py` (design: not shared).

## Result
