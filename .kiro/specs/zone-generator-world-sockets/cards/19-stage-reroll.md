# 19 — A gate failure rerolls only the failing stage

Index entry: `tasks.md` task 19. Requirement 9. Design "Open questions" 5 and `archive.md`
decision 5 (the rules this card is cut to).

## Goal
In `generate_validated`, a rejected attempt on a gated zone type with a random seed retries
the stage at fault instead of the whole zone. The stage is named from what the gate already
reports: passes with Props left out -> Decor (redraw `decor_seed`); fails with no Props and
the failing rooms or corridors lie in an Attachment -> rooms (redraw `rooms_seed`, decor
follows); otherwise a fresh `seed`, as today. At most two stage rerolls per World, then a
fresh `seed`; everything inside the existing attempt cap and timeout. Pinned seeds (any of
the three) fail as they do now. The JSONL line gains the stage blamed and the seeds used.

## Done when
- [ ] With no gate failure, and on every pinned seed, builds are unchanged.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_pipeline.py -q`
- [ ] A forced Decor fault redraws only `decor_seed` (same World and rooms files); a forced
      rooms fault keeps the World file and redraws `rooms_seed`; an unattributed fault and a
      third stage failure draw a fresh `seed`; the JSONL lines name the stage.
      → verify: `python -m pytest tests/test_stage_reroll.py -q`
- [ ] On the Dense and 16-room Graph sweeps, first-try and eventual pass rates are no worse
      than before (numbers in the commit body).
      → verify: `python -m pytest tests/test_decor_builds.py tests/test_graph_layout_build.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`generators/pipeline.py` is a cross-branch hotspot; keep the edit inside the retry loop and
its helpers. Leaving Props out to re-check is a second gate run: only on a failed attempt,
never on a passing one. Don't move the per-room reasons out of `_failure_reasons`; add the
stage beside them. Rerolls re-derive earlier stages from their seeds (Req 5.5), never read
hand-offs back.

## Result
