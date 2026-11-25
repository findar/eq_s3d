# 3 — Affected-only runs: measure testmon

Index entry: `tasks.md` task 3. Requirement 5.

## Goal
Know whether `pytest-testmon` (or the like) cuts an edit's test run, and at what cost.

## Done when
- [ ] Installed into a throwaway venv (`new-worktree.ps1 -Venv`), never the shared environment.
- [ ] Measured: the first run (building its database), and a rerun after a one-line edit in
      each of `generators/layout.py`, `generators/decor/placement.py` and
      `analyzer/traverse.py`. Record tests selected, wall time, and whether it runs under `-n`
      (xdist).
- [ ] A recommendation, with the numbers, reported to the lead. **Don't add the dependency**:
      the lead asks the user, and `requirements.txt` changes only on their yes, in a later
      commit.

## Pitfalls
- Its database must not be committed (`.testmondata` gitignored if adopted).
- Goldens and corpus files are read as data: check that testmon reruns a test when only its
  golden moves.

## Result
