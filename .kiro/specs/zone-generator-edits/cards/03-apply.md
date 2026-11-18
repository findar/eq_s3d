# 3 — Apply the spec-only ops

Index entry: `tasks.md` task 3. Requirement 2.1–2.6. Design "Applying".

## Goal
`generators/edits.py` `apply_edits(doc, ops, seed, version) -> EditResult` for `set_purpose`,
`reroll_room`, `reroll_decor`, `set_decor_level`, `add_lock`, `remove_lock` and `regenerate`;
the resize ops answer "not yet supported" until task 7. Lift `layout.py`'s gating rule
(`_apply_gating`) into a function both the layout and `add_lock` call, without changing any
layout's output.

## Done when
- [ ] Each op changes only its spec fields; the input dict is unchanged; same inputs, same
      result; Affected_Sets as Req 2.2–2.3. → verify: `python -m pytest tests/test_edits.py -q`
- [ ] `add_lock` keeps every key before its lock (the gating solvability check), and an
      unsolvable lock is rejected with a note. Same command.
- [ ] For each partial op, building the edited spec with the parent's stages equals a full build
      of it (footer aside), on a Graph dungeon and a city. Same command.
- [ ] The byte check in `tasks.md` passes (the lifted gating rule changes no layout).
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`rebuild._apply` already handles `decor_seed` and `room_decor_seeds`: reuse its rule
(`room_seeds_after`) rather than copying it.

## Result
