# Design — test-speed

**Tiers.**
- *Quick:* `python -m pytest tests/ -q -m "not slow and not gate" --hypothesis-profile quick`.
  Run on every edit.
- *Full:* `python -m pytest tests/ -q` (every test, `default` profile). Run at a task's close,
  alone.
- *Gate only:* `-m gate`. Run when geometry, layout or the gate changes, and at a task's close
  as part of the full suite.
- *Thorough:* `--hypothesis-profile thorough`. Run where a card asks for it.

**Markers** (`pytest.ini`): `slow` exists. `gate` is new: a test that sweeps builds through
`analyzer.traverse` over seeds or settings (`test_vertical_build`'s stacked sweeps,
`gated_attempts` users). A test can carry both.

**Hypothesis** (`tests/conftest.py`): a `quick` profile with `max_examples=25`, otherwise like
`default`. `pbt_helpers.scaled(n)` already scales by `max_examples / 100`, so every scaled test
runs n/4 examples there. Tests with a literal `max_examples` that are heavy move to `scaled()`.

**Cheaper full suite.** Start from the `--durations` list:
- Find builds that several tests repeat (same plan and seed) and share them through
  `shared_results` or a session fixture.
- Split long parametrized cases so `worksteal` balances them.
- Measure `-n 6` against `-n auto` and `-n 4` for wall time and memory, alone.

**Not here.** Generator speed-ups (cave draw time is a step 27 follow-up), CI, test rewrites
beyond what the timings point at.
