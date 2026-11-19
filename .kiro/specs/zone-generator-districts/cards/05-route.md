# 5 — CLI, Server and sidecar

Index entry: `tasks.md` task 5. Requirements 4.3, 4.4. Design "Plan, prompt and Server".

## Goal
`main.py --districts`; the Server's generate taking `districts`, `district_plan`,
`district_relationship` like the other plan fields, with the A2 note in `warnings`; the sidecar's
`districts` list and each corridor's `threshold`.

## Done when
- [x] A districted dungeon through the route and the CLI: the sidecar's `districts` matches the
      spec, rooms carry their District, Threshold corridors are flagged; a city with Districts on
      builds with the note in `warnings`. → verify: `python -m pytest tests/test_district_route.py -q`
- [x] A rebuild or edit of a districted version keeps its Districts. Same command.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Never `match` with `^…$` on ids (lessons-learned). Old sidecars have no `districts`: the listing
and the page read it as empty.

## Result
✔ bfb4f47 + lead fix · 3716 passed (3715 + the hygiene test, fixed by the lead: `district` off the banned list, flag renamed `--district-theme`)
