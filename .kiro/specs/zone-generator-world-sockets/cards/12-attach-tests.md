# 12 — Attach tests on the World corpus

Index entry: `tasks.md` task 12. Requirements 7.2–7.4. Design "Testing in isolation", P4–P6.

## Goal
The Attach stage tested off the World corpus, with no terrain made, no TER built and no zone gate: hillside Attachments over every recorded hill (rooms in the Envelope, Tunnel covered and within grade, Apron off undiggable cells, at each verticality and a few races), ground Attachments (Kept_Clear, spacing, POIs on reached ground). A `slow` contract test: an Attachment from a loaded Socket equals one from the live World (P4). The cases in `test_outdoor_dungeon_build.py` and `test_site_placement.py` that only check planning or placement move here; the ones that need the built zone stay.

## Done when
- [ ] Attach tests run without `synthesize_landscape`, a TER or the gate (each patched to raise), and pass.
      → verify: `python -m pytest tests/test_attach_hillside.py tests/test_attach_ground.py -q`
- [ ] P4 holds over the corpus.
      → verify: `python -m pytest tests/test_world_corpus.py -q -m slow`
- [ ] The two source files are faster; before and after in the commit body.
      → verify: `python -m pytest tests/test_outdoor_dungeon_build.py tests/test_site_placement.py -q --durations=10 -p no:cacheprovider`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Move a case only when it checks nothing the build adds; a case that reads the built `.eqg` stays. Don't add tests for their own sake (steering): each moved case replaces a slower one.

## Result
✔ 3863387 · 2464 passed
