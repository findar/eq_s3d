# 5 — Rooms get Outlines in graph builds

Index entry: `tasks.md` task 5. Requirements 6, 2.5, 12.3.

## Goal
A graph build asks its style for each room's Outline once doors are known: `shape` gains `auto` and the shapes table, themes gain `walls`, and shipped rules fix what must stay (the temple's nave as `long`). Bridge slots and Tunnels count as doors. Classic, cities and wilderness are untouched.

## Done when
- [ ] Classic, city and wilderness goldens unchanged (W3); graph goldens recaptured in this commit with old and new hashes and the reason.
- [ ] W2: layout (boxes, corridors, levels) identical across styles on a seed.
- [ ] Rooms built per style pass the gate; kinds choose shapes as the table says.
      → verify: `python -m pytest tests/test_outline_build.py tests/test_layout_engine.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
One place sizes rooms (step 7 task 17) and one place draws Outlines; `semantics` shapes a Box before the Outline is drawn, so draw it last. Step 6's rule-format tests pin `rect` as default: change them deliberately.

## Result
