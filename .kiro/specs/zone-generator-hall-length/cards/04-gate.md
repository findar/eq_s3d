# 4 — Gate and bands

Index entry: `tasks.md` task 4. Requirement 5.

## Done when
- [ ] Themed gate sweep (`scripts/sweep_themed_navigability.py`, as step 26 task 4 ran it at
      each Winding, here at `hall_length` `HALL_MIN`, 1 and `HALL_MAX`; `EQ_PATH` set) at
      master's count or better at each setting.
- [ ] Quality bands (`scripts/quality_sweep.py`) under 5% per key at each setting.
- [ ] Draw time at `HALL_MAX` for 30-room Graph caves and outdoor dungeons: median and max.
- [ ] Any new failure: stop and report with its seed before fixing.

## Result
✔ ff3527a · gate 696/695/696 at 0.5/1/3.0, bands <= 3.5% (task 8's runs on the same tree); cave 3.7/5.0 s, outdoor 9.9/17.3 s at 3.0
