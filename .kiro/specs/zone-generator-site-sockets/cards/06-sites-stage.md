# 6 — The Sites stage on point Sockets

Index entry: `tasks.md` task 6. Requirements 3, 6.1–6.4, 7. Design "The Sites stage on points", "Seeds", "Hand-offs", "Bytes".

## Goal
`stages.attach_sites` passes the World's `site` Sockets to `place_sites`, so every wilderness and outdoor-dungeon build with Sites stands its Sites on points. `ATTACH_VERSION` becomes 2 (each Site names its point; v1 refused, named). `sockets_sidecar` lists each point Socket with the Site attached (kind, Group) or none. `wilderness.build._sites` passes the points through. Wilderness and outdoor-dungeon builds with Sites change here: recapture their goldens and the room corpus's Site recordings in this task's commit, with the old and new Site counts per golden in its body. Sites `none`, dungeons and cities don't move.

## Done when
- [ ] P4–P6 on the World corpus: Sites on points, Kept_Clear points skipped, a new `rooms_seed` keeps the World text and moves Sites only among its points; hand-off files round-trip at v2; a v1 Attachments file is refused, named.
      → verify: `python -m pytest tests/test_attach_ground.py tests/test_handoffs.py tests/test_stage_seeds.py -q`
- [ ] Dungeon, city and Sites `none` bytes unchanged; the recaptured goldens pass; the room corpus re-makes the same.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_site_decor_builds.py -q` and `python scripts/record_rooms.py --check`
- [ ] R pooled, the share within 300 u and NN p10 over seeds 1000–1039 at Normal, placement only, before and after, in the commit body (design finding 2's estimate, checked).
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`generators/stages.py` and `generators/wilderness/build.py` are cross-branch hotspots: small edits. The `_sites` cache keys on the World's inputs; the points come from the World, so they should need no new key, but check. Only hashes change in the golden files: if a test's logic needs changing, stop and say so. Re-record corpora in the same commit as the change (step 12 design "Risks").

## Result
✔ 27ff7ee · 3092 passed
