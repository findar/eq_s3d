# 7 — The rooms seed

Index entry: `tasks.md` task 7. Requirements 4.1, 4.2, 4.4, 4.5. Design "Stage seeds", question 4.

## Goal
`rooms_seed` on `ZonePlan` (checked like `decor_seed`) and on `ZoneSpec` (written only when set, so the spec hash holds). `plan_to_spec` uses it for the layout, `_dress_rooms` and the hillside Attachment; the Sites' named seed in `stages.py` becomes it. Textures and trees stay on the World's seed. The sidecar gains a `seeds` block with the resolved `seed`, `rooms_seed` and `decor_seed`. Unset, every build is unchanged.

## Done when
- [ ] P7: bytes unchanged with no `rooms_seed`.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_decor_builds.py tests/test_site_builds.py -q`
- [ ] P8: a new `rooms_seed` on the same seed gives the same World text, the same terrain heights outside the new Entrance's edit and the same textures, and different rooms; on a wilderness, different Sites on the same ground.
      → verify: `python -m pytest tests/test_stage_seeds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`ai/expand.py` is a hotspot. Textures take `ZoneBuilder._base_seed` from `spec.seed`: leave that alone. A spec saved before this step has no `rooms_seed` and must load and rebuild as before. The CLI and server are task 8.

## Result
