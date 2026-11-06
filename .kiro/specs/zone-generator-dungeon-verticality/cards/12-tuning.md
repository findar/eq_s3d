# 12 — Tune from the first look

Index entry: `tasks.md` task 12.

## Goal
The first look (task 10) had no findings, so this task closes the defects the agent tasks left, and anything the user's look at bridges adds:

1. **A stair stub clips a third room's corner** (task 11, `archive.md` "Follow-ups"): on 3-4 of 240 builds, always at 30 rooms, including `tests/test_corridor_clearance.py`'s old seed 7 at moderate. The clearance test catches it; the walk gate doesn't. Fix the route choice, and put seed 7 back beside seed 9 in `FOUND_ON`.
2. **The sidecar labels a bridge flat or ramp** (`connector_record`, task 11): it should say `bridge` with the lower room's id.
3. **Stacked warren's loops** (tasks 6, 17): 0.170 cycles per room against step 6's 0.19 floor, an xfail in `tests/test_topology_embed.py`. Raise them in the rules or the placement so the xfail goes; if that can't hold without breaking warren's other bands, set a stacked-warren band from the survey and say why.

## Done when
- [x] No third-room clip over the 240-build sweep (0 of 240), asserted by a test; seed 7 restored.
- [x] A bridge's connector record says `bridge`; the test in `tests/test_level_sidecar_maps.py` or `tests/test_bridges.py` pins it.
- [x] The stacked-warren xfail is gone.
- [x] Any findings from the user's look at bridges are fixed or recorded as follow-ups.
      → verify: `python -m pytest tests/test_vertical_build.py tests/test_topology_levels.py tests/test_corridor_clearance.py tests/test_bridges.py tests/test_topology_embed.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- The route fix must leave classic byte-identical (goldens).
- A retune of warren must keep tasks 5, 6 and 18's bands.

## Result
✔ 9d4466b · 1429 passed; the user's look at bridges had no findings
