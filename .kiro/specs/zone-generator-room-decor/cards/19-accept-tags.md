# 19 — Accept the proposed tags; condition and feedback

Index entry: `tasks.md` task 19. Requirements 3, 5. Archive decision 25.

## Goal
The user stopped reviewing model by model (decision 25): every model the auto-tagger left at
`use = review` is **accepted by default** and enters builds; the user removes or corrects
models later by feedback, which the lead writes into `rules/decor/tags.toml`.

- `tags.toml` gains a top-level `accept = "proposed"`. With it, an entry whose proposed `use`
  is `review` and which `tags.toml` doesn't set counts as `yes`, its `why` saying "accepted by
  default". A `use` in `tags.toml` (yes or no) always wins. Without the setting, today's rule.
- The tagger proposes `review`, not `no`, for vertex-animated models (they import frozen,
  decision 24); skeletal stays `no`. Re-tag the committed catalogue.
- **Doorway gates stay out:** kind `door` (DOOR1, DOOR620X20, GRATE, KSDOOR101, KSDOOR102R by
  name, plus any the user names) is proposed `no`, why "a doorway gate; doors are runtime
  records (M6)". Recipes never ask for doors.
- **A new Tag `condition`**: `pristine`, `ruined` or `unknown` (proposed `unknown`; names say
  nothing, see the probe in decision 25). Checked like every Tag; shown on the sheet.
  Placement: a room's Props don't mix `ruined` and `pristine` (`unknown` goes with either),
  chosen per room on the room's stream.
- **Parts of an assembly** (pieces stock always places together) are marked by feedback as
  `use = "no"` with `note = "part of <KEY>"`; no new field. Placing assemblies whole is a
  follow-up.
- The tags.toml header documents all of this, including how feedback lines look.

## Done when
- [ ] `python -m pytest tests/test_prop_catalogue.py tests/test_decor_placement.py -q` passes:
      accepted-by-default, a reviewed `no` wins, condition checked and never mixed in a room.
- [ ] `python scripts/topology_rules.py check rules/decor --strict` passes, or every line it
      still names is a kind no stock model in dungeons or cities has (say which).
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
The user's reviewed lines in `tags.toml` (batches 1–4, the frozen banners, CBBARREL103) must
survive unchanged. Don't commit while the full suite runs.

## Result
