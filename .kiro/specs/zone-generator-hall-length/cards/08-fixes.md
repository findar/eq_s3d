# 8 — Long and short hall failures

Index entry: `tasks.md` task 8. Requirements 2 and 5; decision 5.

## Goal
Every seed that passes the gate at `hall_length` 1 passes at 0.5 and 3.0, and the quality bands
stay under 5% per key at 0.5, by fixing root causes, not by narrowing the range or loosening a bar.

## The failures (task 4, `a1661ba`; each passes at 1)
Sweep: `scripts/sweep_themed_navigability.py --only cave warren --layouts classic graph
--verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23 --jobs 6 --hall-length L`.

| L | cell | rooms | seed | check |
|---|---|---|---|---|
| 0.5 | warren graph moderate | 28 | 625239587 | room_15 open seam at (101.5, -69.0, -106.0) |
| 0.5 | cave graph dramatic | 18 | 1068169087 | corr_10 crosses room_11 |
| 3.0 | cave graph flat | 25 | 1425713591 | room_0 footprint_cut, decor_0007 136 u^2 |
| 3.0 | cave graph moderate | 4 | 1704093923 | corr_1 / corr_2 conflict |
| 3.0 | cave graph moderate | 9 | 473448209 | corr_1 headroom 0.2 u at 165.7 u |
| 3.0 | cave graph moderate | 21 | 680460140 | corr_13 headroom 0.4 u at 368.2 u |
| 3.0 | cave graph dramatic | 14 | 839608415 | corr_12 headroom 0.2 u at 404.1 u |
| 3.0 | cave graph dramatic | 25 | 1855383429 | corr_12 stair riser ~3.9 u > 3.0 u |

Bands at 0.5: `quality_sweep --per-key 200 --seed 23 --jobs 6 --hall-length 0.5`,
city/classic/moderate 7.0% (1: 2.5%), 13 new Draws failing `dead_end_ratio` and
`elevation_range`/`elevation_levels` (s371501796, s1960312441, s537966418, s1920360322).

## Done when
- [ ] Each failure diagnosed and grouped by cause; root causes fixed (one commit per cause,
      naming its seeds); a regression test only where cheap.
- [ ] The three sweeps above at 0.5, 1 and 3.0: no seed failing that passes at 1 (≥ 694/696 each).
- [ ] Bands at 0.5, 1, 3.0 under 5% per key.
- [ ] At 1 every zone byte-identical to master, unless a fix is a real bug at 1 too (then name what
      moved and why).
- [ ] Quick tier while working; `-m gate` and the full suite alone at close.

## Pitfalls
- lessons-learned "Geometry / fields" (Z-routes, ramp subdivision, grade by run).
- Don't lower `HALL_MAX` or raise `HALL_MIN` to dodge a failure; if a cause can't be fixed in
  generators/, stop and report.

## Result
