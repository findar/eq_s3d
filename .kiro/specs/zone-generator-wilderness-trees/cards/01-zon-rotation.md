# 1 — ZON object rotation in radians, yaw in the first field

Index entry: `tasks.md` task 1. Design: "Research findings" 5–6, "Build
integration" (`core/zon.py`).

## Goal
`core/zon.py` reads and writes object rotations as radians, and the field that
stock zones use for yaw is the one named `yaw`. Today it treats them as heading
units (0–512) and `place(rz=…)` writes yaw into a tilt field.

## Done when
- [ ] `ZonObject` has `yaw`, `pitch` and `roll` in radians, with `yaw` stored in
      the first rotation field. `place()` takes `yaw`. Nothing else in the repo
      calls the old names (check with a search).
- [ ] A test reads stock broodlands and asserts the yaw of its tree objects
      spans more than ±3 rad while the other two stay within ±0.3 (skipped
      without `EQ_PATH`).
      → verify: `$env:EQ_PATH='F:\everquest_rof2'; python -m pytest tests/test_zon.py -q`.
- [ ] Region `rotation` is checked against stock regions the same way, and
      changed only if it's wrong too (say which in the commit body).
- [ ] Write → read round-trips every field exactly.
- [ ] `python -m pytest tests/ -q` is green.
      → verify: `python -m pytest tests/ -q`.

## Pitfalls
- No generated zone places objects yet, so no existing build bytes should move.
  If a TER/ZON hash test changes, stop and say why.
- Add one line to lessons-learned in the commit body's "for the integrator"
  note (the rotation-unit trap); don't edit steering yourself.

## Result
