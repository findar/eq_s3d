# 5 — A wide, flaring Mouth

Index entry: `tasks.md` task 5. Requirements 6, 7. Split 2026-11-28 (the second kind is task 12).

## Goal
The default way into an outdoor dungeon is a rock Mouth as wide as stock's, flaring out to the Apron, instead of a one-cell Tunnel.

## Done when
- [x] The Mouth's width is drawn 32-96 u, default 48 u (archive decision 2), at the race's scale where the race's Tunnel is taller; it flares from the Tunnel's doorway to the full width at the portal; built on the terrain grid so it stitches exactly; rock cover and grade kept (`python -m pytest tests/test_outdoor_dungeon*.py -q`).
- [x] Walkable both ways: the gate's traverse reaches every room from the Spawn and back out, over the outdoor-dungeon gate sweep at master's count or better (`python -m pytest tests/ -q -m gate`).
- [x] The Spawn stays on open ground with a walkable path to the Apron (task 4's host-size test); the sidecar's Mouth records its width.
- [x] Quick tier; the full suite alone at close.

## Pitfalls
- The Spawn stays on open ground ([outdoor-dungeon requirement](../../zone-generator-outdoor-dungeon/requirements.md), world-sockets P5); task 4's review.
- A ramp is subdivided or the agent can't climb it ([lessons-learned](../../../steering/lessons-learned.md), "A ramp must be SUBDIVIDED").

## Result
✔ bdf8aa2 · 4495 passed, 11 skipped, 5 xfailed (gate 701 passed, 1 xfailed)
