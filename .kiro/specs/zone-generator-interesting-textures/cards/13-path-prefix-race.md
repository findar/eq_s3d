# 13 — Windows path-resolution race in OutputRoot

Index entry: `tasks.md` task 13. Found during task 10 (the first thorough run
in a fresh worktree). Exit criterion 2 (the suites are green).

## Goal
`core/paths.OutputRoot` never decides its own root lies outside itself, so the
parallel test runner's first run in a fresh worktree stops failing at
collection, and `server.app` can always start.

Cause (reproduced 2026-11-01): Python 3.13's `ntpath.realpath` resolves a
path through the OS, then strips the `\\?\` long-path prefix only if a second
lookup returns the same path or fails with the same Windows error as the
first. When parallel workers import `server.app` while `output/web` is being
created, the first lookup can fail with "path not found" and the second with
"file not found" (another worker made `output` but not yet `web`), so the
prefix stays: `\\?\F:\…\output\web` compares unequal to `F:\…\output\web`
and `OutputRoot.path()` raises `OutsideOutputError` naming two identical-
looking paths.

## Done when
- [x] `core/paths._resolve` strips a leftover `\\?\` prefix (and turns
      `\\?\UNC\` back into `\\`), so every `OutputRoot` comparison is on one
      form.
- [x] A test reproduces the race deterministically (a resolve that returns
      the prefixed form) and shows containment still holds.
      → verify: `python -m pytest tests/test_paths.py -q`.
- [x] lessons-learned's "parallel test runner occasionally stumbles" entry
      records the cause and the fix in place of "not reproduced".
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Don't loosen the containment rule; normalise the path form only.
- lessons-learned: the parallel runner's other symptoms (collection mismatch)
  follow from this error in one worker.

## Result
✔ 49acdb2 · 842 passed
