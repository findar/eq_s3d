# 5 — Entrance: Apron, Tunnel and Mouth

Index entry: `tasks.md` task 5. Requirements 4.

## Goal
Flatten an Apron, route a ramp Tunnel to the first room, cut the Mouth and close it with a headwall and jambs, producing one merged TER.

## Done when
- [ ] D3: terrain heights equal the plain Host_Terrain outside the Apron and Mouth.
- [ ] D5: the Tunnel floor meets the Apron flush, and the walk agent can't leave the mesh anywhere at the Mouth.
- [ ] A scratch build's preview is rendered (GLB) and looked at by the worker from outside and inside the Mouth; the commit body says what was seen.
      → verify: `python -m pytest tests/test_entrance.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- This is the risky geometry; keep it a spike that proves the Mouth before the rest builds on it.
- lessons-learned: subdivide ramps so the per-triangle agent can climb them.

## Result
