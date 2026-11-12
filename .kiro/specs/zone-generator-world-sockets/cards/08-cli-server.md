# 8 — The rooms seed on the CLI and the server

Index entry: `tasks.md` task 8. Requirement 4.1. Design "Stage seeds".

## Goal
`--rooms-seed` on `main.py generate` (range-checked, exit 2 on a bad value, like `--decor-seed`); `rooms_seed` in the server's controls and as a top-level request field (what "Reroll rooms" sends, as `decor_seed` is for "Reroll decor"), checked before any write, a bad value a 400 naming the field. The hygiene test's control-name guard learns the new name.

## Done when
- [ ] A CLI build with a rooms seed records it in the sidecar's `seeds` block.
      → verify: `python main.py generate t12 --zone-type outdoor_dungeon --seed 3 --rooms-seed 9 --output output/t12`
- [ ] The server builds with a `rooms_seed`, refuses a bad one with a 400 naming it, and writes nothing on refusal.
      → verify: `python -m pytest tests/test_stage_seeds_controls.py tests/test_hygiene.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`main.py` and `server/app.py` are hotspots. Follow the `decor_seed` path (`_require_decor`, the `RequestValidationError` handler's field list) rather than adding a second way.

## Result
