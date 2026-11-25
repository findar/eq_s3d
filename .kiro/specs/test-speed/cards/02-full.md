# 2 — A cheaper full suite

Index entry: `tasks.md` task 2. Requirement 3, `design.md` "Cheaper full suite".

## Goal
The full suite runs in at most **1200 s wall** at `-n auto`, alone (task 1: 1766 s; the
3308 s baseline was `-n 4`), checking the same things. Fewer builds is the only lever left:
task 1 found the run CPU-bound (20,132 s of worker time over 12 workers).

## Done when
- [ ] From `--durations=0`, the heaviest files (start with `test_vertical_build`,
      `test_walls_mixed`, `test_topology_levels`, `test_properties_pipeline`, `test_site_bands`,
      `test_bridges`) share repeated builds or stop repeating them. Each change and its seconds
      saved go in the commit body.
- [ ] No bar loosened, no seed or case dropped without its name and reason in the commit body.
      The collected count matches task 1's, except for named changes.
- [ ] `python -m pytest tests/ -q` alone, green, at most 1200 s wall; before and after in the
      commit body.
- [ ] `--hypothesis-profile thorough` on the files whose examples changed is green.

## Pitfalls
- Task 1's leads (its commit afee5c4 and archive decision 2): `test_stacked_build_passes_within_the_retries`
  3832 s worker time; single long calls set the wall floor (`test_stock_r_band` 588 s,
  `test_bridge_dungeons_pass_the_gate_first_try` 346 s, `test_mixed_zones_pass_the_gate`
  serial, no `shared_results`); 22 literal `max_examples` ignore the profile; module
  fixtures repeat builds (export, decor_placement, handoffs, versions, district_route).
- `shared_results` and `gated_attempts` (`tests/conftest.py`) already share gate builds across
  workers. Extend them; don't build a second cache.
- A test that builds through `main.main` repoints `tempfile.tempdir` (`_restore_tempdir`).
  Shared builds must not live under a test's `tmp_path`.
- If a speed-up needs generator code, stop and report.

## Result
