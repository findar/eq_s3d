# 8 — Sites controls, sidecar and maps

Index entry: `tasks.md` task 8. Requirements 8.1, 8.3.

## Goal
Sites (None, Sparse, Normal, Dense) and Inhabitants controls on the plan, CLI and web page; prompt words in the rule planner; EQ map lines for Footprints and a label per Site; Sites on the web map.

## Done when
- [ ] Controls round-trip through plan, CLI and server; prompt words pick them.
      → verify: `python -m pytest tests/test_site_controls.py -q`
- [ ] The frontend builds.
      → verify: `cd web; npx vite build`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Movement keys must stay suppressed in form fields (lessons-learned, web viewer).

## Result
