# 11 — Tune from the first look

Index entry: `tasks.md` task 11.

## Goal
Answer the first look's findings in the rules, profiles and embedding. Findings for a later step go to `archive.md` "Follow-ups", not tuned here.

## Done when
- [ ] Each finding is fixed (with a regression test where it's a bug) or recorded as a follow-up.
      → verify: `python -m pytest tests/test_topology_profiles.py tests/test_topology_embed.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- A profile retune moves the G4 bands only if the survey supports it; say which in the commit body.

## Result
