# 4 — Keep the shell's gate result

Index entry: `tasks.md` task 4. Requirements 4.2–4.5. Design "The shell's gate result";
decision 3.

## Goal
Split `analyzer.traverse.validate` into `shell_report` (walk surface, reached faces, seed face,
outline checks, corridor results, the mesh's collidable triangles) and the Props part
(`check_room_props`), `validate` keeping its exact behaviour. A process cache keyed by the TER
bytes' hash holds a few shells and their map outlines; a partial rebuild checks only the Props
against a kept shell and reuses the outline, and runs the full gate (keeping the shell) when none
is kept. The outdoor dungeon splits the same way if it pays; else it takes the full gate (say
which). The wilderness keeps its full gate.

## Done when
- [ ] The partial verdict equals the full gate's, failures included, on passing seeds and on
      seeds where a Prop fails (force one over a door's Throat). → verify: `python -m pytest tests/test_partial_rebuild.py -q`
- [ ] Every gate verdict unchanged. → verify: `python -m pytest tests/test_traversability.py tests/test_traverse_ceilings.py tests/test_traverse_connectors.py tests/test_gate_props.py tests/test_gate_footprints.py tests/test_gate_outlines.py tests/test_gate_features.py tests/test_gate_transitions.py tests/test_layout_engine.py tests/test_decor_builds.py -q`
- [ ] Time: a decor reroll of the 16-room Graph dungeon seed 2 on a warm Server is at most 4 s
      (median of 5); every zone type's partial rebuild beats its full one. Numbers and the
      cache's memory per shell in the commit body.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Key by the TER, not the version: two versions with one TER share a shell. Bound the cache (a
16-room shell may be tens of MB). A shell from another process never exists: the first rebuild
after a restart runs the full gate.

## Result
✔ ea1284d · 3248 passed
