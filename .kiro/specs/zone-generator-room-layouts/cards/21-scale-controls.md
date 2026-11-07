# 21 — Scale controls

Index entry: `tasks.md` task 21. Requirements 15.

## Goal
Finish, Structure, Clutter and Overlay replace Walls and Features.

## Done when
- [x] `ZonePlan`, CLI, server and panel carry them; From rules is the default; a number is a Layer, not a pin: `python -m pytest tests/test_scale_controls.py -q`.
- [x] Old plans load as Req 15.2 says.
- [x] `python -m pytest tests/ -q` is green, and the frontend builds: `cd web; npx vite build`.

## Pitfalls
Hygiene allowlists name controls. Step 8's and 9's tests name `walls` and `features`: the plan fields stay for old plans, so they should hold.

## Result
✔ ce9ba60 · 1948 passed
