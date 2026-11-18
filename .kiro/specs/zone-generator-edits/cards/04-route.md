# 4 — The edit route and CLI

Index entry: `tasks.md` task 4. Requirement 3. Design "Route".

## Goal
`POST /api/edit` and `main.py --edit`, building the next version through `generators/rebuild.py`
(partial) or `generate_validated` (full), with the sidecar `edit` block and the versions
listing's `edit` field.

## Done when
- [x] Text and ops requests each make the next version; the sidecar has the `version` and `edit`
      blocks; the listing shows the edit. → verify: `python -m pytest tests/test_edit_route.py -q`
- [x] Every `applied: false` case of Req 3.2 leaves the zone folder byte-identical (hash every
      file before and after). Same command.
- [x] A partial edit that changes the TER is built in full (`StaleStages`), and either way the
      version equals a full build of the edited spec. Same command.
- [x] Two edits at once on one zone: the second is a 429 and changes nothing. Same command.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Never `match` with `^…$` on ids (lessons-learned). Don't commit while the full suite runs (the
server-staleness test).

## Result
✔ 30d6799 · 3504 passed
