# 4 — Responses, edits, listing and CLI

Index entry: `tasks.md` task 4. Requirement 4. Design "Route, CLI, listing".

## Goal
The Quality_Block in generate, rebuild and edit responses (reason in `warnings` when degraded),
`edit_outside_bands`, the listing's `quality`, and the CLI's 25.9 lines.

## Done when
- [x] Each response's `quality` equals the version's sidecar entry; degraded reasons appear in
      `warnings`, passed ones don't. → verify: `python -m pytest tests/test_quality_route.py -q`
- [x] An edit that leaves the bands is accepted as `edit_outside_bands`. Same command.
- [x] The CLI prints the reason, count and entries for a degraded build and exits 0. Same command.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Never `match` with `^…$` on ids (lessons-learned). Old versions have no `quality`: the listing
says null, not an error.

## Result
✔ 97dbfc3 · 3561 passed
