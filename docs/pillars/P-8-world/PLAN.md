# P-H World — plan

> **Draft.** This pillar is new: the umbrella spec has no World requirements. Multi-zone worlds
> and zone lines wait on the user's design review (ROADMAP: "the user wants to review that design
> before it's chosen"). The requirements below are proposals for that review, not approved.

## Goal

A zone stops being an island: it sits in a World that knows what attaches where, so several
zones can be generated as neighbours, joined by zone lines that land in the right place on both
sides, and a dungeon, a town or a camp can be placed into a landscape deliberately.

## Scope

- The World stage and its Sockets (`generators/world.py`, `generators/stages.py`): today a
  single zone's World.
- Zone lines between generated zones (the reserved `door` Socket kind).
- More than one attached thing per World (several dungeons under one landscape; an exact Mouth
  Socket chosen by the World).
- The stage hand-offs as the World's saved form (`<name>.world.json`, `.attach.json`).

## Non-goals

- What any one zone looks like or how it's laid out (P-E, P-G).
- Server-side zone-line rows beyond what Export already writes (P-C) until H-1 is designed.

## Requirements (proposed IDs, for the user's review)

| ID | Requirement (draft) | Status now |
|---|---|---|
| P-H.1 | A World describes one or more zones and how they connect, saved as versioned JSON | One zone per World (step 12) |
| P-H.2 | Zone lines: a `door` Socket on each side of a connection, landing the player at a matching point; exported as EQEmu zone-point rows | `door` kind reserved; none made |
| P-H.3 | A World chooses its attach points (an exact Mouth Socket) and can hold more than one dungeon | The Attach stage picks the Mouth inside the hillside Socket; one dungeon per World |
| P-H.4 | Each stage reads only the World and earlier hand-offs (no stage re-derives the landscape) | Mostly: two outdoor-dungeon functions still re-derive it (OPEN H-4) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| 12 | [`zone-generator-world-sockets`](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) | done 2026-11-13 | 59 | A build as stages off World Sockets (`root`, `hillside`, `ground`; `door` reserved), saved hand-offs, stage seeds and blame-based rerolls |

Also served by: step 13 (point `site` Sockets, World version 2; P-G). Step 12 is filed here
because its Socket model is the base this pillar builds on; it equally served P-F (partial
rebuild) and P-B (stage blame on a gate failure). The review may move it to Engineering.
