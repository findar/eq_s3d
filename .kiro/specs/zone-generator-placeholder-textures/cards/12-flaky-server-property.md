# 12 — Flaky server property and the parallel test-runner hang

Index entry: `tasks.md` task 12. Found in task 8 (commit `dd5f24f`). Exit
criterion 2 (the thorough suite is green).

## Goal
Find why `tests/test_server.py::test_build_file_paths_served_or_refused`
(step 1b Property 18: build-file paths are served or refused by the rules)
failed once in task 8's thorough run, and fix the root cause in the server or
the test, not by loosening the property. Find, too, why the test runner's
parallel workers sometimes hang or collect different tests at start-up.

What's known: the failure came from a parallel thorough run of the whole
suite (737 passed, 1 failed). It didn't reproduce in 6 serial thorough runs
with fixed Hypothesis seeds, or in one parallel thorough run of
`tests/test_server.py`. A second parallel run of that file hung with no
workers left. Earlier runs in steps 2 and 3 twice stopped at collection with
"Different tests were collected between gw0 and gw2", and once with an
`OutsideOutputError` while collecting `tests/test_properties_pipeline.py`
(which imports `server.app` at module level).

## Done when
- [ ] The cause of the Property 18 failure is named in the commit body, with
      the failing example if one is found, and fixed at the root; or, if it
      can't be reproduced after a documented search, the test records how it
      shares state with other tests in a worker and stops doing so.
- [ ] The collection mismatch and the start-up hang are explained, and fixed
      or recorded in lessons-learned with a workaround.
- [ ] Three thorough runs in a row are green.
      → verify: `python -m pytest tests/ -q --hypothesis-profile=thorough`
        (three times).
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Keep Property 18's rules as they are; it's the server's path contract.
- Thorough runs take about 22 minutes; run them in the background and stop a
  hung one (check for pytest processes left behind).
- If the fix needs files outside `Owns`, stop and ask.

## Result
