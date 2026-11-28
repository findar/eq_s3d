# 7 — Numbered pillars, one requirement namespace, a technical writer's pass

Index entry: `tasks.md` task 7.

## Goal
The user, reviewing task 1: "Can we use numbers instead of letters with the pillar, So P-1 instead of P-A. Also where do the requirements in the requirements column come from? a technical writer should be giving a review pass on these documents to make sure that all references have links or clear indication what they reference".

## Done when
- [ ] Pillars numbered P-1 to P-9 (P-1 Web app ... P-7 Engaging, P-8 World, P-9 Engineering); folders renamed with `git mv`; every mention updated. Open-item IDs follow (e.g. B-1 becomes 2-1, or another scheme the writer picks and states).
- [ ] One requirement namespace: the umbrella's Requirements 1-33 (`.kiro/specs/zone-generator/requirements.md`) keep their numbers, written `Req 4`, each a link to its heading; pillar-proposed requirements (World, Engineering drafts) continue at Req 34 onward, marked "proposed", until the umbrella adopts them. No `P-B.4`-style IDs. Each pillar README row says where its requirements come from.
- [ ] Writer's pass over every file this spec created: every reference is a link or says plainly what it is. Covers file and code paths (relative links), Req numbers, umbrella and step decisions (link to the entry), step numbers (link to the spec), open-item IDs (link to the item), commit hashes (with what the commit did), terms of art (defined once, in a glossary in `docs/ARCHITECTURE.md` or linked to one). A link check (script output in the commit body) finds no broken link.
- [ ] Plain-language pass: short sentences, no unexplained abbreviations, consistent names for the same thing.
- [ ] The authoring hand-off (the manual finishing pass the README promises) gets its own open item under P-6 Iterative feedback.
- [ ] `docs/STYLE.md`: the house rules the pass applied (reference and link rules, ID schemes, plain language), short, for later docs to follow.

## Result

✔ ea09662 · docs only
