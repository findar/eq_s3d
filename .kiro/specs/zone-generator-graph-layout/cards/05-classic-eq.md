# 5 — Base set classic_eq and the temple layer

Index entry: `tasks.md` task 5. Requirements 5.1, 5.3. Design "Rule-set files".

## Goal
`rules/topology/classic_eq.toml` (start graph, rules, recipe, placement `spring`), `layers/temple.toml` (the nave with side chapels), and `themes.toml`, tuned until the grown graphs fall in the survey's classic bands.

## Done when
- [ ] The files load and pass every check; each is commented so it reads as an example.
- [ ] G6: over a fixed seed list and room counts 5–30, `classic_eq`'s shape measures and Size_Class mix fall inside the finding 5 classic bands (means and p10–p90, not every graph).
- [ ] A temple build applies `nave`; the base file is unchanged.
      → verify: `python -m pytest tests/test_ruleset_classic_eq.py tests/test_topology_ruleset.py -q`
- [ ] The recipe's weights and shares and the bands they hit are in the commit body.

## Pitfalls
- Small n (1–4) can't show a shape: the start graph covers them (design).

## Result
