# 20 — Site Props in builds

Index entry: `tasks.md` task 20. Requirements 10.1, 11. Archive decisions 10, 28–35.

## Goal
Task 11 dresses a Site from its RoomContext, but built zones don't carry the result:
`builder.decor_for` returns None for zones without rooms (every wilderness) and
`wilderness/build._gate_zon` builds without decor. Wire it:

- `decor_for` also places Site contexts (`room_context.site_contexts`) in wilderness and
  outdoor-dungeon builds, packed and gated like room Props (ZON objects, lights, sidecar).
- **The open-ground screen as data:** many stock models are open shells the wilderness gate
  reads as enterable or as cutting off ground (carts, chests, a third of the rocks; task 11
  refused 533 by running the gate in its test, 5–6 min). Compute it once with
  `python scripts/prop_catalogue.py screen`, store a per-model measured flag in
  `catalogue.json` (metadata only, no client art), load it in `catalogue.py`, and have
  placement skip unscreened-out models at Sites (placement still imports no gate). The P11
  test then reads the flag instead of running the gate per model.
- **The Decor control applies to wilderness** (Site Props): add it to `DECOR_ZONE_TYPES` and
  show it on the page for wilderness. Decor `none` and Sites `none` each keep step 10's bytes.

## Done when
- [ ] Built wilderness and outdoor-dungeon zones carry Site Props and pass the gate on 40
      seeds at Normal and Dense; Decor none is step 10's bytes.
      → verify: `python -m pytest tests/test_site_decor_builds.py tests/test_site_props.py -q`
- [ ] The P11 test runs in under a minute (the screen is data).
- [ ] `cd web; npx vite build` succeeds; `python -m pytest tests/ -q` is green.

## Pitfalls
`builder.py` is a cross-branch hotspot: keep edits small. The screen must be reproducible
from the install (`screen` rewrites only its own field).

## Result
