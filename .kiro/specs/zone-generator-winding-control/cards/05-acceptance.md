# 5 — Acceptance section

Index entry: `tasks.md` task 5.

## Goal
`docs/ACCEPTANCE.md` "Step 26 — Winding control": the same cave seed at Winding 0, 1 and max in 3D
and on the map, a warren at max, the slider and the words, and a fortress unchanged.

## Done when
- [x] The section is written, and every case was run with its seed on agent servers (8020–8050).
- [x] Thorough run `python -m pytest tests/ -q --hypothesis-profile=thorough -n 4`, failures named
      in the commit body.

## Result
✔ e17a1ad · 4082 passed, 6 skipped (thorough, -n 4)
