# 11 — The clustering target and the gate, held

Index entry: `tasks.md` task 11. Requirements 4, 5.3, 8. Design "Holding the clustering target", "The gate and first try".

## Goal
`tests/test_site_bands.py` asserts the biome's targets from `biomes.toml` (plains: R pooled 0.50–0.95, the share within 300 u 33–65 %, pooled NN p10 108–191 u) on the built zones of seeds 1000–1039 at Normal; at Dense, that Sites still group (archive decision 11), in place of `STOCK_R` and the all-zone `SPACING_P10` (both still printed); Sites per area and Structures per Site keep step 10's bands. A fast placement-only check of the same targets on Worlds alone (Req 4.4). `test_stock_r_band` checks the plains band too. The gate's first try (wilderness seeds 1000–1039, outdoor dungeons 0–39, Normal and Dense) no worse than step 12's, and outdoor dungeons at Normal with a Site on 35+ planning seeds, built.

## Done when
- [ ] The fast check passes, unmarked.
      → verify: `python -m pytest tests/test_site_bands.py -q -m "not slow"`
- [ ] The bands, the gate's first try and the Sites cost pass; the numbers at master before task 6 and after, in the commit body.
      → verify: `EQ_PATH='F:\everquest_rof2' python -m pytest tests/test_site_bands.py tests/test_site_builds.py -q`
- [ ] The full suite stays under 25 min and the fast under 8, idle.
      → verify: `python -m pytest tests/ -q --durations=10 -p no:cacheprovider` and the same with `-m "not slow"`

## Pitfalls
If one target is just out while the other two are in, stop and report the three numbers (design "Risks": two Sites is a small sample); don't tune Group sizes against the test. Share builds through `shared_results` as the file does now (step 12 task 21). Prefer fixing a root cause over loosening a band (steering).

## Result
✔ ddcb8b1 · 3106 passed (full 22.9 min, fast 2294 in 5.7 min, idle)
