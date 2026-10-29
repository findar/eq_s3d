# 9 — Release prep: reproducibility, budget, acceptance checklist

Index entry: `tasks.md` task 9. Old tasks 12.8, 12.9, 14.1, 15.1, 15.2.
Requirements 5.3, 13.2, 13.3.

## Goal
Get everything ready for the final human pass. Prove that a wilderness build is
reproducible from its seed and fits the time budget, and write the
wilderness section of the acceptance checklist the human will walk.

## Done when
- [ ] **Property 16 (seeded reproducibility):** the same pinned seed gives the
      same TER, and no seed gives a fresh one. `.eqg`/`.glb` need not be
      byte-identical (project rule).
      → verify: `tests/test_wilderness_build.py`, docstring `Feature: zone-generator-wilderness, Property 16: ...`.
- [ ] A `@pytest.mark.slow` timing test shows a full wilderness generate
      finishes well under 5 minutes, and that `DEFAULT_TIMEOUT_S["wilderness"]`
      in `generators/pipeline.py` covers it.
- [ ] `docs/ACCEPTANCE.md` gains a section "Step 1 — Wilderness (open Karana)",
      built from the card-04 checklist plus water, textures and sidecar, with
      the case/seed table (including any seeds task 5 moved).
- [ ] `python -m pytest tests/ -q` is green, and the thorough profile
      (`--hypothesis-profile=thorough`) is green once. Record its duration in Result.
- [ ] `cd web; npx vite build` succeeds.

## Result
✔ a0982a5 · 511 passed · thorough 511 passed in 11m25s (ran alongside the default suite)
