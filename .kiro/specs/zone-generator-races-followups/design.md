# Design — zone-generator-races-followups (roadmap step 32)

Written at master `fbfe1a9`. Verify against the code before each task: it moves.

- **Breach rate (task 1):** step 31 task 17 replaced `_stretch_thresholds` with `_fit_thresholds`
  in `generators/layout.py` and bounded breaches at twice the pair's longest link in the smaller
  race's H. Candidates now fail on span. Lever: place intruder rooms nearer host walls (the
  spring run of cross edges, or a pull of intruder rooms toward host rooms they could breach)
  before breach candidates are drawn, and let a breach between Levels carry a ramp as other
  corridors do. Measure which candidates fail and why first.
- **Build-order leak (task 2):** find the module-level state (cache, RNG, registry) that a
  previous build leaves behind; fix so each build starts clean. Archive follow-up at step 31
  task 14: a race-less classic Districts zone differs in two decor entries and its `.zone.json`.
- **Map returns (task 3):** `CorridorSpec` gains a written-only-when-set flag for a drop's return
  (from `drop_returns` in layout); `mapview` reads it instead of inferring.
