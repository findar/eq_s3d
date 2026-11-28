# 1 — Proposal: architecture, pillar map, open items

Index entry: `tasks.md` task 1. Requirements 1, 2, 3.

## Goal
Everything the user needs to judge the structure before any file moves: the architecture doc, each pillar's PLAN and DESIGN drafts, and the open-items list.

## Done when
- [ ] `docs/ARCHITECTURE.md`: pipeline, ZoneSpec IR, module map, stage hand-offs, north-star rules; verified against the code, not the old specs.
- [ ] `docs/pillars/<id>-<name>/PLAN.md` and `DESIGN.md` for all nine pillars: PLAN has goal, scope and non-goals, requirements (umbrella IDs kept), and every one of the 32 roadmap steps and 37 specs assigned to a pillar as a slice (a table, with status); DESIGN describes current behaviour with links to code. `DECISIONS.md` splits the umbrella's 48 decisions and the step specs' decisions by pillar (links, not copies, where a spec archive holds the text).
- [ ] `OPEN.md` (root) and each pillar's `OPEN.md`: every step spec's archive follow-ups and ROADMAP's carried lists, deduplicated, each checked against the code (fixed ones listed separately with their commit), plus the 2026-11-27 gaps (requirements.md item 3).
- [ ] A short `docs/pillars/README.md` with the balance: slices and commits per pillar, so the drift into P-G/P-E shows.
- [ ] Nothing moved or deleted; existing files untouched.

## Result

✔ 394c6b4 · docs only
