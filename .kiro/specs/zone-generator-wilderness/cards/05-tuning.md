# 5 — Tune from the first look (time-boxed)

Index entry: `tasks.md` task 5.

## Goal
Fix what the human found in task 4. This card is deliberately thin: its
contents come from task 4's Result. If a finding needs a design change rather
than a tuning change, split it into its own task in `tasks.md`; don't absorb it
here.

## Findings to address
<!-- copied from card 04 Result, one checkbox each, with the case/seed -->
- [ ] _(fill from task 4)_

## Done when
- [ ] Every finding above is either fixed or split out as a new task.
- [ ] Properties 1–15 are still green. **Don't weaken an assertion to fit a
      new setting.** If a property breaks, the setting is wrong, or the property
      was hiding a real bug.
- [ ] Changed values are recorded in `archive.md` "Decisions" (old → new and
      why), and every seed whose output moved is listed in Result for task 10.
- [ ] `python -m pytest tests/ -q` is green.

## Levers (where they live)
- Zone size / cell size: `DEFAULT_ZONE_SIZE`, `DEFAULT_CELL_SIZE` — `generators/wilderness/matrix.py`
- Rim band / set-back: `RIM_BAND_FRACTION`, `SETBACK_FRACTION` — `generators/wilderness/synth.py` / `bowl.py`
- Erosion: `HYDRAULIC_*`, `THERMAL_*`, `FLOW_EXPONENT` — `generators/field/terrain.py`, `synth.py`
- A full build takes ~0.26 s, so there is plenty of budget headroom for a
  bigger zone or a finer grid.

## Result
<!-- worker: one line + moved seeds -->
