# 7 — Walls control, sidecar and maps

Index entry: `tasks.md` task 7. Requirements 11.

## Goal
The Walls control through the plan, CLI, server and page; sidecar `walls`, room `shape`, `fill`, `outline`; the map SVG draws Outlines; a test pins that EQ map files follow shaped rooms.

## Done when
- [ ] Each setting reaches the build; a bad value is a usage error naming the choices; old saved plans still load.
- [ ] The map draws an Outline, and the EQ map's wall lines lie on it.
      → verify: `python -m pytest tests/test_walls_controls.py -q`
- [ ] `python -m pytest tests/ -q` is green; the frontend builds.

## Pitfalls
Hygiene allowlists. Frontend-only changes still run the Python suite.

## Result
