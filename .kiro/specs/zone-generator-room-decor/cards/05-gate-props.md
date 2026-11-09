# 5 — The room gate learns placed models

Index entry: `tasks.md` task 5. Requirements 2.

## Goal
Before any generator places one, the room gate (dungeon, city, outdoor-dungeon interiors, every Level) judges placed models from their own collidable triangles placed by their ZON objects, closed meshes or not: a Footprint cutting reached floor from the entrance, a Throat or door narrowed below the clear width, an unreached POI. The design recommends obstacles in the traversal agent (`world_triangles`); with no placed models the answer is today's.

## Done when
- [ ] P1: a hand-built room case of each failure fails, named, pinned as an example; one uses an open, oddly wound mesh like stock's.
      → verify: `python -m pytest tests/test_gate_props.py -q`
- [ ] P2: on builds with no placed models the gate's answer and report are unchanged.
      → verify: `python -m pytest tests/test_gate_props.py tests/test_layout_engine.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Judge from the models, not the placer's record. Stock meshes aren't closed: step 10 decision 9's "inside a solid" rule assumes they are (design "Importing a model"). Watch the cost: step 8's gate work once took builds from 1 s to 18 s.

## Result

