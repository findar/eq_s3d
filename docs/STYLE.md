# Docs style

House rules for the project's docs: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md), the pillar files
under [`docs/pillars/`](pillars/README.md), [`OPEN.md`](../OPEN.md) and every doc written after
them. Project-docs task 7 applied them to those files. Later docs follow them too.

## Where docs live

- **Docs are tool-agnostic.** They live in plain folders ([`docs/`](.), the repo root), never in a
  folder that belongs to one tool or agent product. Today's specs and steering still sit under
  [`.kiro/`](../.kiro). Project-docs tasks 3, 4 and 6 move them: specs to
  `docs/pillars/<P-n>/slices/S-<step>-<name>/`, the always-on rules to a root `AGENTS.md`, the
  lessons to `docs/LESSONS.md`. Until then, link to today's [`.kiro/`](../.kiro) paths so the links work;
  the task that moves a file rewrites the links to it.

## IDs

### Pillars

`P-1` to `P-9`, each with a folder `docs/pillars/P-<n>-<name>/`. Write the number and name
together on first mention in a file ("P-3 Usable in RoF2 and EQEmu"), then the number alone.

### Requirements

A requirement ID is `<doc>-Req-<n>[.<criterion>]`. The `<doc>` part is a short name for the
requirements document the ID comes from. There are three levels:

| Level | Document | Short name | Example |
|---|---|---|---|
| Product | the umbrella spec's [`requirements.md`](../.kiro/specs/zone-generator/requirements.md) | `ZG` | `ZG-Req-4`; acceptance criterion 4.3 is `ZG-Req-4.3` |
| Pillar | each pillar's `PLAN.md` | `P-<n>` | `P-2-Req-1` |
| Slice | a step spec's `requirements.md` | `S-<step>` | `S-31-Req-2` |

- **Cite one level up, and only one.** A slice cites its pillar's requirements. A pillar cites
  `ZG` requirements. [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) and the pillar README cite `ZG` at the whole
  requirement (`ZG-Req-4`), not its criteria.
- **Don't list children where the parent covers them.** Write `ZG-Req-22`, not
  `ZG-Req-22.5` to `ZG-Req-22.7`, unless one criterion alone is meant.
- **Every pillar requirement names its parent**, linked: "Parent: [ZG-Req-4](../.kiro/specs/zone-generator/requirements.md#requirement-4-traversability-gate)".
- **The way down is a table, not prose.** Which slices served a pillar requirement goes in the
  "Traceability" table in that pillar's `PLAN.md`. Project-docs task 5 has
  [`scripts/task_status.py`](../scripts/task_status.py) generate it.
- **Drafts with no parent** (P-8 World, part of P-9 Engineering) are pillar requirements whose
  parent is "proposed: [ZG-Req-34](pillars/README.md#zg-req-34)" and onward. The proposed parents are listed in one place, the
  pillar README's [Proposed product requirements](pillars/README.md#proposed-product-requirements),
  until the umbrella adopts them.
- **[ZG-Req-33](../.kiro/specs/zone-generator/requirements.md#introduction)** (the `cave` Purpose) is cited by the umbrella but was never written
  ([P-9-14](pillars/P-9-engineering/OPEN.md#p-9-14)). Its links go to the umbrella's
  introduction, which cites it.
- **History stays as written.** Old step specs that cite "zone-generator Req 4.3" are not
  rewritten; the traceability tables map them.

### Open items

`P-<n>-<k>`: the pillar number, then the item's number in that pillar's `OPEN.md`, for example
`P-2-1`. Each item has an anchor (`<a id="p-2-1"></a>` in its row), and every mention elsewhere
links to it. Numbers are never reused. A fixed item moves to that file's "Fixed" table and keeps
its number in the history.

### Slices, steps and milestones

- A slice is a step's spec. Its future ID is `S-<step>` (`S-31`); step numbers are already
  unique.
- Write "[step 31](../.kiro/specs/zone-generator-district-races/tasks.md)" and link it to the spec's `tasks.md`. Write "[step 31 archive](../.kiro/specs/zone-generator-district-races/archive.md)" when you mean
  its `archive.md` (most often its "Follow-ups"), and link there.
- [M0](../.kiro/specs/zone-generator-m0-hygiene/tasks.md) and [M1](../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) link to their specs. [M2](../.kiro/specs/zone-generator/design.md#delivery-plan) to [M6](../.kiro/specs/zone-generator/design.md#delivery-plan) link to the umbrella design's
  [Delivery Plan](../.kiro/specs/zone-generator/design.md#delivery-plan).
- In a table row or a line of prose, link the first mention of each target; later mentions of
  the same step in that line stay plain.

### Decisions

- **Umbrella decisions** are a numbered list under one heading of the umbrella design. Write
  "[umbrella decision 19](../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)" and link it to
  [Decisions Made in This Revision](../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).
  A lettered part is "[umbrella decision 21](../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part c".
- **Slice decisions** are numbered in each step's `archive.md`. Write "[step 17 decision 5](../.kiro/specs/zone-generator-export/archive.md#decisions)" and
  link it to that archive's "Decisions" heading.
- Never write a bare "decision 5": say whose.

## References

- **Paths** are written in backticks and linked with a relative link:
  [`generators/layout.py`](../generators/layout.py). Write the path from the repo root, not a
  bare file name. Patterns with placeholders (`output/web/<zone>/v<n>/`) and files that don't
  exist yet are not linked; call the latter "planned".
- **Commit hashes** are 7 characters in backticks, always with what the commit did:
  "`6781622` ([step 32](../.kiro/specs/zone-generator-races-followups/tasks.md) task 2: the stock model cache is keyed by actor, not mesh)". A snapshot
  is "master `c3d9b99` (2026-11-27, the commit that opened the project-docs spec)".
- **Other docs' sections** are named in quotes and linked to the heading: [ROADMAP](../ROADMAP.md)
  ["Known issues"](../ROADMAP.md#known-issues--smaller-fixes).
- **Sources** say who or what recorded an item: "[step 18 archive](../.kiro/specs/zone-generator-edits/archive.md)", "the user, 2026-11-22",
  "gap 2026-11-27", "found by [project-docs task 1](../.kiro/specs/project-docs/cards/01-proposal.md)". Never "found here" or "this proposal".
- **Anchors** are GitHub's heading slugs: lower case, punctuation dropped, spaces turned into
  hyphens, `-1`, `-2` added for repeats. An explicit `<a id="...">` is used where a heading
  can't serve (table rows).
- **Check links before committing**: every relative link must reach a file, and every `#anchor`
  a heading slug or an explicit `id` in it. Put the checker's summary line in the commit body.

## Terms

- Terms of art are defined once, in the [glossary](ARCHITECTURE.md#glossary). Files under
  [`docs/pillars/`](pillars) point to it in their first lines. A new term goes into the glossary in the same
  commit that first uses it.
- Capitalise the project's own nouns (District, Socket, Draw, Gate for a lock).
- One name for one thing: the **walk gate** and the **format gate** (together, "the gates"); the
  **umbrella spec**; **Purpose**, not theme or archetype (the field is still `dungeon_theme`);
  **P-9 Engineering**, not "Engineering" or "ENG".

## Plain language

- Short sentences, one point each.
- Spell out an abbreviation the first time a file uses it, or define it in the glossary:
  binary space partitioning (BSP), continuous integration (CI).
- Words, not symbols: "at most 3 u", not "≤ 3 u"; "passes when every room is reached", not
  "pass ⇔ reached".
- Units with every number: `u` (EverQuest units), `H` (a race's body height), seconds as `s`.
- Dates as YYYY-MM-DD.
- Say what is not done or not checked, plainly: "never built", "not looked at in 3D".
