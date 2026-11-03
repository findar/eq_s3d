# 2 — LayoutEngine seam, byte-identical

Index entry: `tasks.md` task 2. Requirements 2. Design "The seam".

## Goal
Move Job A (scatter, separate, connect) behind `LayoutEngine` with `ClassicEngine` as the first engine, and add Job B's three touch points (entry, role size bias, edge relations) as no-ops for classic, proven byte-identical by goldens captured before any code moves.

## Done when
- [ ] First commit: `tests/test_layout_engine.py` with sha256 goldens of the Zone_Spec JSON and the `.eqg` contents (footer aside) for dungeon, city, wilderness and outdoor_dungeon on pinned seeds, passing on unchanged code.
- [ ] `generators/layout_engine.py` has `LayoutContext`, `EngineResult`, `LayoutEngine`, `ClassicEngine` and the `ENGINES` registry; `LayoutGenerator(..., engine=None)` uses classic; edges carry a relation (`any` for classic).
- [ ] The goldens still pass after the move.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_hygiene.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- rng order is the whole game: the moved code must draw from `ctx.rng` in exactly the order it does today. The Zone_Spec golden catches a slip.
- `_separate_rooms` stays on `LayoutGenerator`; Job B calls it after role biasing. Engines get it through the context.
- The Envelope's `entry` (step 5) wins over an engine's entry for an outdoor dungeon.
- lessons-learned "Two `.eqg` writes are never byte-identical": compare `bytes[:-4]` or the archive entries.

## Result
