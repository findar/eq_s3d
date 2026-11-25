# 1 — Tiers: markers, the quick profile, the quick command

Index entry: `tasks.md` task 1. Requirements 1 and 2, `design.md` "Tiers", "Markers",
"Hypothesis".

## Goal
One command runs the quick tier in at most 10 minutes, alone; every heavy test carries a marker.

## Done when
- [ ] `pytest.ini` registers `gate`; every sweep through the gate over seeds or settings carries
      it (listed in the commit body).
- [ ] Every test that takes at least 10 s in the full suite's `--durations=0` carries `slow`,
      `gate` or both; the newly marked ones and their seconds are in the commit body. Start
      from the 28 in the baseline (`archive.md` decision 1).
- [ ] `tests/conftest.py` has a `quick` profile (`max_examples=25`, otherwise `default`).
- [ ] Measured alone, each in the commit body (wall, passed, deselected, peak memory):
      `python -m pytest tests/ -q -m "not slow and not gate" --hypothesis-profile quick` at
      `-n auto`, `-n 6` and `-n 4`. The quick tier is **≤ 600 s** at the best count;
      `pytest.ini`'s `-n` is set to that count if it beats `auto`.
- [ ] `python -m pytest tests/ -q --collect-only` collects the same count as master at start
      (4113 at the baseline), named.
- [ ] The full suite alone, at the chosen `-n`, green; wall in the commit body.

## Pitfalls
- lessons-learned "Parallel agents must not share a commit-message file, nor run full suites at
  once": check for a running `pytest tests/` or sweep before timing.
- `scaled(n)` floors: `scaled(4)` under `quick` is 1. Check that a property with very few
  examples still draws its edge case, or keep it at `default`.
- Don't lower a test's examples under `default`: that's task 2's call, and only with a reason.

## Result
