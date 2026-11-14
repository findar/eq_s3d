# 8 — Retire the area path and recipe spacing

Index entry: `tasks.md` task 8. Requirement 3.5. Design "The Sites stage on points", question 5.

## Goal
With every caller on points (task 6), remove what the area Socket needed: `place_sites` without points (and the legacy `(land, ter)` form), `_choose_centre`, `terrain_of`, and the recipes' `spacing` field (from `rules/sites/sites.toml`, the loader and its header comment). The loader refuses `spacing` afterwards, naming it. Placement tests that drove the legacy form move to Worlds with points, each checking what it did. No bytes move.

## Done when
- [ ] No caller of the removed functions is left; a recipe with `spacing` is refused, named.
      → verify: `python -m pytest tests/test_site_placement.py tests/test_site_rules.py -q`
- [ ] Bytes unchanged.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_site_decor_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Grep the whole repo (tests and scripts included) before deleting: `scripts/stage.py` and the band test may import a name. A test moved off the legacy form keeps its property (old -> new in the commit body); don't add tests for their own sake.

## Result
✔ 7dc1efd · 3103 passed
