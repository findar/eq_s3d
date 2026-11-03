# 4 — Rewrite driver, recipes and layers

Index entry: `tasks.md` task 4. Requirements 4. Design "Growing the graph".

## Goal
`rewrite.py`: the matcher (kinds, match edges, `match_hops`, `when`), applying a rule with reattachment, and the recipe driver (stage budgets, the room-count check, the invariants, the step cap), recording every application.

## Done when
- [ ] The matcher finds every placement of 1–3 node matches; reattachment moves outside edges as declared, including a split across several targets.
- [ ] G3 and G4 over seeds and n = 1–30 with small test sets: no `Area` left, exactly n rooms, connected, degree ≤ 4, loops of 3–5; `TopologyError` at the cap names set, stage and cap; same seed, same graph.
- [ ] G5: a layer's rules and stages take part in a build of its theme, and the base set's loaded data is unchanged.
      → verify: `python -m pytest tests/test_topology_rewrite.py -q`

## Pitfalls
- Deterministic: candidate matches in sorted order before the rng picks; no set iteration order leaks into choices.
- Don't import or generalise `generators/wilderness/rewrite.py` (design: not shared).

## Result
