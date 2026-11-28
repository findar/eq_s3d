# P-6 Iterative feedback — plan

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

## Goal

A user refines the zone they have instead of starting over: "make the boss room bigger",
"reroll the decor", "undo that". An edit changes only what was asked, never leaves a broken zone,
and every version stays reachable.

## Scope

- Versions of a zone (`output/web/<zone>/v<n>/`, parent links) and the version stepper.
- Rerolls and partial rebuilds from saved stages ([`generators/rebuild.py`](../../../generators/rebuild.py)).
- Chat edits: interpretation ([`ai/edits.py`](../../../ai/edits.py), [`ai/llm_edits.py`](../../../ai/llm_edits.py)), application
  ([`generators/edits.py`](../../../generators/edits.py), [`generators/resize.py`](../../../generators/resize.py)), the Feedback box ([`web/src/feedback.ts`](../../../web/src/feedback.ts)).
- Undo and redo.
- Keeping one room's decor from the room view ("Use in zone").

## Non-goals

- Server-side sessions, their expiry times and eviction: dropped by [umbrella decision 37](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) (the
  versions on disk are the history).
- Editing rule recipes from the page ([P-6-7](OPEN.md#p-6-7) is a candidate, not in scope yet).

## Requirements

The parents were amended by [umbrella decisions 35](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) and [37](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).

| ID | Requirement | Parent | Status now |
|---|---|---|---|
| <a id="p-6-req-1"></a>P-6-Req-1 | Feedback text is turned into edits on the current zone | [ZG-Req-18](../../../.kiro/specs/zone-generator/requirements.md#requirement-18-sessions-and-feedback-interpretation) | Built on versions, with no Session store ([umbrella decision 37](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part A1): a rule interpreter turns text into edit ops; a language model is optional, with the rules as fallback |
| <a id="p-6-req-2"></a>P-6-Req-2 | An edit changes only what was asked, and an edit that fails is not applied | [ZG-Req-19](../../../.kiro/specs/zone-generator/requirements.md#requirement-19-edit-application-and-acceptance) | Built for purpose, locks, room and decor rerolls, decor level, regenerate and four resizes. Six ops answer "not yet supported" ([P-6-1](OPEN.md#p-6-1)) |
| <a id="p-6-req-3"></a>P-6-Req-3 | History, undo and redo | [ZG-Req-20](../../../.kiro/specs/zone-generator/requirements.md#requirement-20-history-undo-and-redo) | Built: undo opens the parent version and redo the newest child, on the page with no server call; an edit made from an older version branches from it |

## Traceability

Which slices served each requirement. ([`scripts/task_status.py`](../../../scripts/task_status.py)
will generate this table after [project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md).)

| Requirement | Served by |
|---|---|
| [P-6-Req-1](#p-6-req-1) | [step 18](../../../.kiro/specs/zone-generator-edits/tasks.md) |
| [P-6-Req-2](#p-6-req-2) | [step 16](../../../.kiro/specs/zone-generator-partial-rebuild/tasks.md) (partial rebuild), [step 18](../../../.kiro/specs/zone-generator-edits/tasks.md) |
| [P-6-Req-3](#p-6-req-3) | [step 16](../../../.kiro/specs/zone-generator-partial-rebuild/tasks.md) (versions), [step 18](../../../.kiro/specs/zone-generator-edits/tasks.md) (undo and redo) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| 16 | [`zone-generator-partial-rebuild`](../../../.kiro/specs/zone-generator-partial-rebuild/tasks.md) | done 2026-11-17 | 19 | A reroll is the next version; decor rebuilds from the parent's saved stages, byte-identical to a full build |
| 18 | [`zone-generator-edits`](../../../.kiro/specs/zone-generator-edits/tasks.md) | done 2026-11-18, acceptance skipped | 22 | Chat edits on versions; undo and redo along parent links |

Also served by: [step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) (the stage hand-offs that make partial rebuild possible; P-8), [step 15](../../../.kiro/specs/zone-generator-decor-rules/tasks.md)
(the room view and its "Use in zone"; P-5), [step 19](../../../.kiro/specs/zone-generator-quality/tasks.md) (an edit outside the quality bands is built
and marked `edit_outside_bands`; P-7).

Nothing here has been looked at in person: both slices skipped their acceptance pass.

The manual finishing pass that the [project README](../../../README.md) promises (the output is
"a starting point for a manual authoring pass") has no support yet; see [P-6-8](OPEN.md#p-6-8).
