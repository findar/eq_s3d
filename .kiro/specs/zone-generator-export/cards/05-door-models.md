# 5 — Door models in builds with Gates

Index entry: `tasks.md` task 5. Requirements 3.3, 5. Design "Doors"; task 2's Door model decision.

## Goal
Two cases, set by task 2's decision:
- **Packed:** `generators/doors.py` imports the Door model (as decor imports stock models), and
  the builder packs it into builds with Gates, with no ZON placement (a door is a runtime record).
- **Global model:** this task only checks that the name the SQL writes is that model, and closes
  with no build change.

## Done when
- [ ] A build with Locks 2 holds the Door model (or task 2's global is named); a build with no
      Gates is byte-identical to before. → verify: `python -m pytest tests/test_door_models.py -q` and the byte check in `tasks.md`
- [ ] Builds with Gates still pass the gate and the format check; their recaptured hashes and why
      are in the commit body.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Never place the door as geometry or a ZON object. The model comes from the install at build time,
like decor; nothing from the install is committed.

## Result
