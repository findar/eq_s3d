# P-8 World — plan

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

> **Draft.** This pillar is new: the umbrella spec has no World requirements. Multi-zone worlds
> and zone lines wait on the user's design review ([ROADMAP "Pick up here"](../../../ROADMAP.md#-pick-up-here-next-session), "Later candidates":
> the user wants to review that design before it is chosen). The requirements below are
> proposals for that review, not approved. Their parents are proposed product requirements,
> listed in the [pillar README](../README.md#proposed-product-requirements).

## Goal

A zone stops being an island: it sits in a World that knows what attaches where, so several
zones can be generated as neighbours, joined by zone lines that land in the right place on both
sides, and a dungeon, a town or a camp can be placed into a landscape deliberately.

## Scope

- The World stage and its Sockets ([`generators/world.py`](../../../generators/world.py), [`generators/stages.py`](../../../generators/stages.py)): today a
  single zone's World.
- Zone lines between generated zones (the reserved `door` Socket kind).
- More than one attached thing per World (several dungeons under one landscape; an exact Mouth
  Socket chosen by the World).
- The stage hand-offs as the World's saved form (`<name>.world.json`, `.attach.json`).

## Non-goals

- What any one zone looks like or how it's laid out (P-5, P-7).
- Server-side zone-line rows beyond what Export already writes (P-3) until [P-8-1](OPEN.md#p-8-1) is designed.

## Requirements (drafts, for the user's review)

| ID | Requirement (draft) | Parent | Status now |
|---|---|---|---|
| <a id="p-8-req-1"></a>P-8-Req-1 | A World describes one or more zones and how they connect, saved as versioned JSON | proposed: [ZG-Req-34](../README.md#zg-req-34) | One zone per World ([step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md)) |
| <a id="p-8-req-2"></a>P-8-Req-2 | Zone lines: a `door` Socket on each side of a connection lands the player at a matching point; exported as EQEmu zone-point rows | proposed: [ZG-Req-35](../README.md#zg-req-35) | The `door` kind is reserved; none is made |
| <a id="p-8-req-3"></a>P-8-Req-3 | A World chooses its attach points (an exact Mouth Socket) and can hold more than one dungeon | proposed: [ZG-Req-36](../README.md#zg-req-36) | The Attach stage picks the Mouth inside the hillside Socket; one dungeon per World |
| <a id="p-8-req-4"></a>P-8-Req-4 | Each stage reads only the World and the earlier hand-offs; no stage works the landscape out again | proposed: [ZG-Req-37](../README.md#zg-req-37) | Mostly: some outdoor-dungeon functions still work it out again ([P-8-4](OPEN.md#p-8-4)) |

## Traceability

Which slices served each requirement. ([`scripts/task_status.py`](../../../scripts/task_status.py)
will generate this table after [project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md).)

| Requirement | Served by |
|---|---|
| [P-8-Req-1](#p-8-req-1) | [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md), [step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) (World version 2) |
| [P-8-Req-2](#p-8-req-2) | none (the kind is reserved by [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md)) |
| [P-8-Req-3](#p-8-req-3) | [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) (the Mouth inside the hillside Socket) |
| [P-8-Req-4](#p-8-req-4) | [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| 12 | [`zone-generator-world-sockets`](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) | done 2026-11-13 | 59 | A build as stages off World Sockets (`root`, `hillside`, `ground`; `door` reserved), saved hand-offs, stage seeds and blame-based rerolls |

Also served by: [step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) (point `site` Sockets, World version 2; P-7). [Step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) is filed here
because its Socket model is the base this pillar builds on. It equally served P-6 (partial
rebuild) and P-2 (stage blame on a gate failure). The review may move it to P-9.
