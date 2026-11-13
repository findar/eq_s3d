# 21 — The fast suite and the band sweeps

Index entry: `tasks.md` task 21. Requirement 7.5. Design finding 2; `archive.md` decision 8
(revised 2026-11-13: fast suite under 8 min, full under 25).

## Goal
Task 13 shares the gate sweeps' builds. This is the rest of finding 2. Task 20 measured the
fast suite at 14.6 min (idle), against 8. (a) Share builds in `test_decor_bands.py` and
`test_site_bands.py` the way task 13 does. (b) Shrink the fast suite's long tests without
marking them `slow` (decision 8 keeps them in the fast suite): `test_properties_layout.py`
(`test_flush_openings`, `test_elevation_grade_cap`, `test_connectivity_and_roles`),
`test_topology_embed.py::test_big_races_keep_their_loops`, `test_pipeline.py::
...test_backend_fallback_reaches_warnings_and_sidecar`, `test_properties_pipeline.py::
test_availability_follows_enabled`, `test_topology_levels.py`. Find why each is slow first
(a build where a plan would do; a sweep where a few seeds pin the property; a Hypothesis
strategy drawing huge cases) and fix that.

## Done when
- [ ] The fast suite is under 8 min and the full suite under 25 min, idle.
      → verify: `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q --durations=30 -p no:cacheprovider` and the same with `-m "not slow"`
- [ ] No check lost: each changed test checks what it did (old -> new, in the commit body).
- [ ] `python -m pytest tests/ -q` is green; `--hypothesis-profile thorough` keeps its examples.

## Pitfalls
Same as task 13. A Hypothesis test's `max_examples` under the default profile is the fast
suite's budget; the thorough profile is not, so don't cut that one. If a test can't get fast
without losing its property, stop and report it with its time.

## Result
