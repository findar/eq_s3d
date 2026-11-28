# P-1 Web app and controls — decisions

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Links, not copies. The umbrella decisions are numbered as in the umbrella design's
[Decisions Made in This Revision](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision);
each number below links there. Slice decisions are numbered in each step's `archive.md`.

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| [2](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | One expansion path | Controls build a `ZonePlan` (`from_controls`) and go through `plan_to_spec` like prompts; the golden test found 72/72 cases unchanged |
| [19](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Zone vocabulary | One field per descriptive axis with closed value lists; "theme" is only a UI label. The `zone_type` rename landed in [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md); the content renames were planned for [M3](../../../.kiro/specs/zone-generator/design.md#delivery-plan) and did not land |

## Slice decisions

| Slice | Where | Topics |
|---|---|---|
| [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) waves 2 and 5 | [`zone-generator-m1-controls-traversability/design.md`](../../../.kiro/specs/zone-generator-m1-controls-traversability/design.md), its [`tasks.md`](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) decisions | rename boundaries, mode resolution, an HTTP 400 answer before anything is written, controls golden test |
| [Step 14](../../../.kiro/specs/zone-generator-web-cleanup/tasks.md) | [`zone-generator-web-cleanup/archive.md`](../../../.kiro/specs/zone-generator-web-cleanup/archive.md) | one Generate, controls that don't apply left out of the request |

## Settled (don't relitigate)

- The prompt never silently overrides the controls ([umbrella Known Limitation 7](../../../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them), fixed in [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md)).
- The target short name is not a generation control; it is chosen at Export ([umbrella decision 20](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), P-3).
