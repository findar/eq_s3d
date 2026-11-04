# 6 — The rules go up and down

Index entry: `tasks.md` task 6. Requirements 5, 6. Design "Rule format".

## Goal
The shipped rule sets gain vertical rules (`descent`, `stair_hall`, `gallery`), the Verticality control scales them (`flat` 0, `moderate` 1, `dramatic` 2), and built dungeons fall in finding 7's bands.

## Done when
- [ ] Vertical rules in `classic_eq` and `warren` (and the temple layer if it suits), commented as examples; `python scripts/topology_rules.py check` passes and `draw` shows the vertical edges.
- [ ] V7: over a seed sweep, the BUILT dungeons' Stacked_Share, level count and span at `moderate` fall in finding 7's bands; `flat` is one Level; `dramatic` is at or above `moderate` on each.
- [ ] Step 6's shape bands and fidelity bars still pass.
      → verify: `python -m pytest tests/test_ruleset_classic_eq.py tests/test_ruleset_warren.py tests/test_topology_levels.py tests/test_topology_embed.py -q`

## Pitfalls
- Step 6's rule-format traps (`docs/TOPOLOGY_RULES.md` "Traps"): the rest stage needs growth rules that work from finished rooms; sizes on kept nodes are ignored.
- The Verticality control reaches the engine through `ai/expand.py`; classic keeps its existing elevation mapping unchanged.

## Result
