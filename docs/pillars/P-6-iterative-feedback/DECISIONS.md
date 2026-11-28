# P-6 Iterative feedback — decisions

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Umbrella decision numbers link to the umbrella design's
[Decisions Made in This Revision](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| [11](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Feedback uses full spec snapshots per version | Exact undo; a deterministic per-edit rng; rejects edits that fail the hard gates. (Its element-keyed mesh cache was never built; stage hand-offs took its place) |
| [35](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 16](../../../.kiro/specs/zone-generator-partial-rebuild/tasks.md): a reroll is the next version; decor rebuilds from saved stages | Byte-identical to a full build; the gate re-checks only what changed |
| [37](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 18](../../../.kiro/specs/zone-generator-edits/tasks.md): the rest of [M4](../../../.kiro/specs/zone-generator/design.md#delivery-plan) on the versions | (A1) no Session store: the versions are the history; (A2) undo and redo on the page; (A3) the op vocabulary and the six "not yet supported" ops |

[Umbrella decision 13](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) (session security: expiry times, evicting the least recently used session,
history caps, a lock per session) was mostly dropped with the Session store by umbrella decision
37, part A1. Binding to loopback only and the explicit CORS list (which web origins may call the
server) still stand; see P-9.

## Slice decisions

| Slice | Where |
|---|---|
| [Step 16](../../../.kiro/specs/zone-generator-partial-rebuild/tasks.md) | [`zone-generator-partial-rebuild/archive.md`](../../../.kiro/specs/zone-generator-partial-rebuild/archive.md) ([step 16 decision 2](../../../.kiro/specs/zone-generator-partial-rebuild/archive.md#decisions): byte-identical; [step 16 decision 5](../../../.kiro/specs/zone-generator-partial-rebuild/archive.md#decisions): the rest of [M4](../../../.kiro/specs/zone-generator/design.md#delivery-plan) later) |
| [Step 18](../../../.kiro/specs/zone-generator-edits/tasks.md) | [`zone-generator-edits/archive.md`](../../../.kiro/specs/zone-generator-edits/archive.md) ([step 18 decision 5](../../../.kiro/specs/zone-generator-edits/archive.md#decisions): one build per zone at a time; [step 18 decision 10](../../../.kiro/specs/zone-generator-edits/archive.md#decisions): a `rooms_seed` rebuild drops edits) |
