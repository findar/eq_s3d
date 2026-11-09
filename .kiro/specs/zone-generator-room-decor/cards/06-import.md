# 6 — Import a catalogued model

Index entry: `tasks.md` task 6. Requirements 4.

## Goal
`generators/decor/stock.py`: a catalogue entry to a `.mod` and DDS textures, read from the install: vertices, triangles, UVs and passable flags unchanged (WLD 0x10 to `FLAG_PASSABLE`), one material per texture, cached by mesh hash. Animated models are refused, named.

## Done when
- [ ] P4: for a sample of entries across Categories, the imported triangles, UVs, flags and texture pixels equal the stock model's, and the `.mod` round-trips.
      → verify: `python -m pytest tests/test_prop_import.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Tests need the install: skip without `EQ_PATH`, as the survey tests do. Masked and transparent textures (webs, flames) keep their alpha.

## Result

