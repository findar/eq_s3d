# 3 — Host terrain with a Host_Hill

Index entry: `tasks.md` task 3. Requirements 3.

## Goal
The Design_Matrix can be asked for a Host_Hill (one connected raised region of a given footprint) and a bowl size; the wilderness guarantees still hold.

## Done when
- [x] A host-hill request at the default size yields one connected hill region with the requested footprint plus margin, and an open approach on the Entrance side.
- [x] The bowl, rim, water and lava properties pass for host-hill builds (reuse the wilderness property tests' checks on a sample of seeds).
- [x] Without the request, wilderness builds are byte-identical.
      → verify: `python -m pytest tests/test_host_terrain.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- The matrix is the layout authority; synth must not move the hill.
- Size scales the matrix grid, not the cell size (the TER resolution stays).

## Result
✔ f7561ec · 935 passed
