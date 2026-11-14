# 2 — The clustering rules

Index entry: `tasks.md` task 2. Requirement 2.7. Design "The clustering rules, as data".

## Goal
`rules/sites/biomes.toml` gains `[biomes.plains.groups]` with task 1's values: `gap`, `sizes` (share of Groups by size, summing to 1), `within` ([low, high] u), `spacing`, and the targets `target_r`, `target_in_gap`, `target_nn_p10`. `generators/sites/rules.py` reads it strictly, as it reads the rest (every bad value named: shares that don't sum to 1, a low above a high, a size under 1, an unknown key), and exposes it on the biome. Nothing reads it yet; no build changes.

## Done when
- [ ] The plains block loads; each bad value is refused, named.
      → verify: `python -m pytest tests/test_site_rules.py -q`
- [ ] The rule tooling still passes.
      → verify: `python scripts/topology_rules.py check rules/sites`
- [ ] Bytes unchanged.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Follow the loader's existing pattern for `density` and `inhabitants` rather than adding a second way. A biome with Site rules but no `groups` block is an error, not a default: only plains exists.

## Result
