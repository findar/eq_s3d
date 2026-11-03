# 5 — Base set classic_eq and the temple layer

Index entry: `tasks.md` task 5. Requirements 5.1, 5.3. Design "Rule-set files".

## Goal
`rules/topology/classic_eq.toml` (start graph, rules, recipe, placement `spring`), `layers/temple.toml` (the nave with side chapels), and `themes.toml`, tuned until the grown graphs fall in the survey's classic bands.

## Done when
- [x] The files load and pass every check; each is commented so it reads as an example.
- [x] G6: over a fixed seed list and room counts 5–30, `classic_eq`'s shape measures and Size_Class mix fall inside the finding 5 classic bands (means and p10–p90, not every graph).
- [x] A temple build applies `nave`; the base file is unchanged.
      → verify: `python -m pytest tests/test_ruleset_classic_eq.py tests/test_topology_ruleset.py -q`
- [x] The recipe's weights and shares and the bands they hit are in the commit body.

## Pitfalls
- Small n (1–4) can't show a shape: the start graph covers them (design).
- The `"rest"` stage must hold growth rules as well as `finish`: an earlier stage that ends short passes its budget on, and a rest stage of `finish` alone can't reach n (`grow` raises `TopologyError`, cap None). Task 4's commit `ee79cc0` explains budgets and picking.

## Result
✔ cf08918 · 1100 passed
