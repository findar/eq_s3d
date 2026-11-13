# 20 — An outdoor dungeon reads one landscape

Index entry: `tasks.md` task 20. `archive.md` decision 9 (the user, 2026-11-13: fix in step 12).

## Goal
Today an outdoor dungeon's spec mixes two landscapes (found by task 3). `outdoor_dungeon_spec`
takes `safe_point`, `regions` and `water_level` from `wilderness_spec(..., landform=
DEFAULT_HOST_HILL)`, the Landform as REQUESTED. The TER, the planner, the Sites, the trees and
the bowl gate use `landscape_for(spec)`, the Landform as PLACED. They differ on 29 of seeds 0-39
(seed 0: 312 vertices up to 476 u apart, 32 cell types, the Spawn's Z). Make the spec's Spawn,
regions and water come from the placed landscape, the one the World's terrain is, so the World
holds one landscape and `world_of` no longer has to re-ask for `DEFAULT_HOST_HILL` and cross-check.
Every affected outdoor dungeon changes once; dungeons, cities and wildernesses don't.

## Done when
- [ ] For seeds 0-39, an outdoor dungeon's Spawn, regions and water level equal the placed
      landscape's, and its Spawn stands on the TER's ground (one test over the World corpus
      plus a seed sweep that builds no TER, read from the World).
      → verify: `python -m pytest tests/test_world.py tests/test_world_corpus.py -q`
- [ ] Bytes move only for outdoor dungeons: dungeon, city and wilderness goldens unchanged;
      the outdoor-dungeon golden in `test_layout_engine.py`, the World corpus's `outdoor_*`
      recordings and the room corpus's `outdoor_*` recordings re-recorded in this task's commit,
      with the old and new Spawn for each in the commit body.
      → verify: `python -m pytest tests/test_layout_engine.py -q; python scripts/record_worlds.py --check; python scripts/record_rooms.py --check`
- [ ] The outdoor dungeon's first-try gate rate over seeds 0-39 is no worse (numbers in the
      commit body), and its Site and bowl checks pass.
      → verify: `python -m pytest tests/test_outdoor_dungeon_build.py tests/test_attach_hillside.py tests/test_attach_ground.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Find which of `regions` and `water_level` the placed landscape gives before assuming; a region
list built from the requested Landform may name places the placed one doesn't have. The Apron
still lowers the Spawn after this (`stages.apply_edits`). Wilderness specs keep their own
landscape: don't change `wilderness_spec` for wildernesses. Re-record corpora in the same commit
as the change (design "Risks", "Corpora go stale"). A user may have a saved outdoor-dungeon spec
from before: it should still build (say in the commit body what it builds).

## Result
