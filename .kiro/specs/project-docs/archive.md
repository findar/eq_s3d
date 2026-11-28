# Archive — project-docs

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Pillars are the umbrella's outcome pillars P-A to P-G, plus P-H World and Engineering** (the lead,
   2026-11-27): outcome pillars say what the project is for; code areas get design docs under them. The
   user's review (task 2) can change the set.
2. **Pillars are numbered, and requirement IDs name their document** (the user, at the task 1
   review: "Can we use numbers instead of letters with the pillar, So P-1 instead of P-A", then "if a
   requirement is in a seperate requirement doc, we have a shorthand for the doc name and then
   reference the number from it"). Pillars are P-1 to P-9 (P-8 World, P-9 Engineering). A requirement
   is `<doc>-Req-<n>[.<criterion>]` at three levels: `ZG` (the umbrella), `P-<n>` (a pillar's
   `PLAN.md`), `S-<step>` (a slice). References go one level up only; the way down is a traceability
   table. Drafts with no parent get a proposed parent from ZG-Req-34 on, listed in the pillar README.
   Open items are `P-<n>-<k>`. Full rules: `docs/STYLE.md`.

## Follow-ups
