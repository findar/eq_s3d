# 1 — Stock clustering, measured

Index entry: `tasks.md` task 1. Requirements 4.1, 2.7. Design finding 1.

## Goal
Commit the measurement finding 1 was drafted from, so its numbers come from the repo. `scripts/site_clustering.py` reads the surveyed zones with `scripts/site_survey.py`'s own code (`cluster`, `site_measures`, `ground_of` with its cache) and prints, per zone: Sites, dry ground, Clark–Evans R (as `tests/test_site_bands.clark_evans`), R against random points on the zone's own dry cells (R_mc, with the share of draws as clustered), Sites per Group and the share within the Group gap, and nearest-Site p10/p50; then the same per biome group, and the plains' Group sizes, within-Group and Group-centre spacing at 200, 300 and 400 u. Confirm or correct the values the design proposes for `biomes.toml` (gap 300, sizes, within 112–227, spacing 600, the three targets).

## Done when
- [ ] The script prints the zone, group and Group-size tables, and its plains and all-zone R reproduce the plains 0.50–0.95 and `STOCK_R` (0.64–1.64).
      → verify: `python scripts/site_clustering.py --eq-path F:\everquest_rof2`
- [ ] Finding 1 holds the script's numbers (any that differ from the draft's corrected) and the `biomes.toml` values task 2 writes.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
The biome groups are a reading of the zones, not data in the survey: say so in the script. R_mc uses random draws: fix the generator's seed. The walked-ground cache lives under `output/site_survey/cache/` (gitignored, per worktree): copy it from the main checkout or let `ground_of` rebuild it (slow). No tests: a script that writes a finding.

## Result
