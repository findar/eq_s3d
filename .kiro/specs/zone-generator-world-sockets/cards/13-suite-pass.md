# 13 — The suite pass

Index entry: `tasks.md` task 13. Requirement 7.5. Design finding 2, "Testing in isolation".

## Goal
Bring the suite inside finding 2's targets. Finding 2: the time is gate sweeps. The vertical, graph-layout, walls and Features sweeps each build and gate their own seeds per zone type; build each (zone type, seed, controls) once in a session-shared cache (`tests/conftest.py`) that all four read, and where a sweep compares first-try rates, run the Attach stage's own check (Req 7.4) on the full seed list and the zone gate on a fixed few. Each test keeps the property it states.

If the targets are still missed, the lead adds task 21 for the rest of finding 2: `test_decor_bands.py` and `test_site_bands.py` (share builds the same way), and the three slow tests not marked `slow` (`test_properties_layout.py::test_flush_openings`, `test_topology_embed.py::test_big_races_keep_their_loops[giant]`, `test_pipeline.py::...test_backend_fallback_reaches_warnings_and_sidecar`).

## Done when
- [ ] The fast and full suites are inside the targets, on an idle machine.
      → verify: `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q --durations=30 -p no:cacheprovider` and the same with `-m "not slow"`
- [ ] No check lost: each moved test checks what it did (old test -> new, in the commit body).
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Prefer fixing a root cause over loosening a test (steering). A shared build must not be changed by the tests that read it; xdist workers don't share memory, so a session cache is per worker (a disk cache under the pytest tmp root is the other choice: say which and why). The thorough profile (`--hypothesis-profile thorough`) is not the target; don't trade its examples away.

## Result
