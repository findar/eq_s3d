# 2 — Socket and World types

Index entry: `tasks.md` task 2. Requirements 1.1, 1.4, 1.5, 5.3. Design "The Socket", "The World".

## Goal
`generators/world.py`: the `Socket`, `Terrain` and `World` dataclasses of the design, with a versioned JSON form (`VERSION = 1`) and stable text (sorted keys, one layout), so a recorded World diffs cleanly. Floats are written exactly (Python `repr`), never rounded; height grids as nested lists, masks as `#`/`.` strings as `room_context` writes them, cell types as a code raster. Reading a file of another version raises, naming the file and both versions. The kinds `root`, `hillside` and `ground` are made by later tasks; `door` is accepted on read and made by nothing (design question 3). No stage logic here.

## Done when
- [x] Hand-built Worlds of each Socket kind round-trip through JSON exactly, values like `0.1 + 0.2` and `-0.0` included; another version is refused, named.
      → verify: `python -m pytest tests/test_world.py -q`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Don't reuse `room_context._r`: it rounds to 2 places, which moves rooms (design Risks "Exact floats"). JSON has no NaN; say in the module how a missing height is written and read. Keep `world.py` free of imports from `generators.wilderness` and `generators.outdoor_dungeon`, so a test can load a World without them.

## Result
✔ 9e6d153 · 2392 passed
