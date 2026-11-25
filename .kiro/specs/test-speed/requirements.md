# Requirements — test-speed (roadmap step 28)

STATUS: done (closed 2026-11-25). The user, 2026-11-24: "How can we optimize the tests so they don't take so long ?
That should be a priority to speed up iteration", then "Start as soon as it merged" (after step
27 task 12).

Baseline (step 27 task 12's suite, `-n 4`, alone): 4113 collected, 4103 passed, 11 skipped,
**3308 s wall**; collection about 36 s. The 150 slowest tests (≥ 21 s each) take 6287 s, about
48% of worker time; `test_vertical_build` alone takes 2459 s. 28 of the 150 (1197 s) are not
marked `slow`. Numbers in `archive.md`.

1. **A quick tier for every edit.** One documented command runs every test that builds no
   multi-seed sweep and no full Pipeline, in **at most 10 minutes wall, alone**, and catches the
   regressions a unit or single-build test can catch.
2. **Tiers by marker.** `slow` (one build-level property or Pipeline run) and `gate` (a sweep:
   many builds through the gate) select the heavy tests; no heavy test is unmarked. The full
   suite still runs every test.
3. **The full suite gets cheaper, not weaker.** Shared builds, fewer duplicate builds and
   right-sized Hypothesis examples, with no bar loosened, no case dropped without naming it,
   and the same collected count except for named changes.
4. **The rules say which tier when.** Steering names the tier for every edit, for a task's
   close, and for geometry, layout or gate changes.
5. **Affected-only runs are tried.** `pytest-testmon` (or the like) is measured; it's adopted
   only if it works with the parallel runner and the user agrees to the new dependency.
