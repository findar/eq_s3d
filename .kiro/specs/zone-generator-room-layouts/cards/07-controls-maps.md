# 7 — Features control, sidecar and maps

Index entry: `tasks.md` task 7. Requirements 8, 6.4.

## Goal
The Features control through plan, CLI, server and page; sidecar records; map SVG draws Features and POIs; EQ map files gain lines for free-standing ones (if question 6 says so).

## Done when
- [ ] Each setting reaches the build; `none` equals step 8's rooms and walls; bad values name the choices; old plans load.
      → verify: `python -m pytest tests/test_features_controls.py -q`
- [ ] `python -m pytest tests/ -q` is green; the frontend builds.

## Pitfalls
Hygiene allowlists. Frozen map schematic strips Outlines; it may need to strip Features too.

## Result
