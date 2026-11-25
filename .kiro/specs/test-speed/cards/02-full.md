# 2 — A cheaper full suite

Index entry: `tasks.md` task 2. Requirement 3, `design.md` "Cheaper full suite".

## Goal
The full suite runs in at most **2000 s wall**, alone (baseline 3308 s), checking the same
things.

## Done when
- [ ] From `--durations=0`, the heaviest files (start with `test_vertical_build`,
      `test_walls_mixed`, `test_topology_levels`, `test_properties_pipeline`, `test_site_bands`,
      `test_bridges`) share repeated builds or stop repeating them. Each change and its seconds
      saved go in the commit body.
- [ ] No bar loosened, no seed or case dropped without its name and reason in the commit body.
      The collected count matches task 1's, except for named changes.
- [ ] `python -m pytest tests/ -q` alone, green, at most 2000 s wall; before and after in the
      commit body.
- [ ] `--hypothesis-profile thorough` on the files whose examples changed is green.

## Pitfalls
- `shared_results` and `gated_attempts` (`tests/conftest.py`) already share gate builds across
  workers. Extend them; don't build a second cache.
- A test that builds through `main.main` repoints `tempfile.tempdir` (`_restore_tempdir`).
  Shared builds must not live under a test's `tmp_path`.
- If a speed-up needs generator code, stop and report.

## Result
