# 8 — Decor controls, decor seed, sidecar and maps

Index entry: `tasks.md` task 8. Requirements 9.1–9.4.

## Goal
A Decor control (None, Sparse, Normal, Dense) and a decor seed on the plan, CLI and page; prompt words; a "Reroll decor" button on a built zone; Props' Footprints on the EQ map and Props on the web map and side panel, read from the built `.eqg`.

## Done when
- [ ] P9: a decor seed changes only Props (ZON objects, lights, Prop models); the rest of the archive is byte-identical.
      → verify: `python -m pytest tests/test_decor_controls.py -q`
- [ ] The frontend builds.
      → verify: `cd web; npx vite build`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
The page's lists come from the server, not hard-coded (step 6 follow-up).

## Result

