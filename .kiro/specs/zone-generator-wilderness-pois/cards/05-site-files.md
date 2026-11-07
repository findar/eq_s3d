# 5 — Site recipes as data

Index entry: `tasks.md` task 5. Requirements 5.

## Goal
`rules/sites/` (`sites.toml`, `inhabitants.toml`, `biomes.toml`) and a strict loader: kinds with Structures, arrangement, ground, likes and POIs; Inhabitants with material sets, variants and Weights; biomes with their Inhabitant mix. The design's six kinds and four plains Inhabitants, with weights from finding 1 once task 1 lands (placeholders until then, marked as such).

## Done when
- [ ] P6: every bad value named by file, entry and field; every kind has a recipe; chance is weight over sum.
      → verify: `python -m pytest tests/test_site_rules.py -q`
- [ ] The check and draw tooling runs on the shipped files.
      → verify: `python scripts/topology_rules.py check rules/sites`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Model the loader on step 9's (`generators/room_layouts.py`, `generators/room_scales.py`): same error shape, same Weights rule.

## Result
