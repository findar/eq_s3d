# rules/topology

Rule sets for the graph layout engine: base sets (`*.toml`), theme layers
(`layers/*.toml`) and the theme map (`themes.toml`). The format, the shipped
sets as worked examples and the traps are in the authoring guide,
[`docs/TOPOLOGY_RULES.md`](../../docs/TOPOLOGY_RULES.md).

```bash
python scripts/topology_rules.py check                                  # every file here
python scripts/topology_rules.py dry-run classic_eq --graphs 50 --rooms 5-20
python scripts/topology_rules.py draw classic_eq --out output/rules/    # writes classic_eq.html
```

Vertical rules (step 7): a rule whose replacement has an `above` or `below`
edge joins rooms on different Levels by a stair. The Verticality control
scales them: `flat` leaves them out (one Level), `moderate` uses the weights
as written, `dramatic` doubles them. The shipped examples are `passage`,
`descent`, `stair_hall`, `gallery` and `undercroft` (classic_eq), `tunnel`,
`descent`, `stair_hall`, `gallery` and `sunken_burrow` (warren), and `crypt`
(the temple layer).
