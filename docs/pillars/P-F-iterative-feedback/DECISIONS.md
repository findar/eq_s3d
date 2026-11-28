# P-F Iterative feedback — decisions

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| 11 | Feedback uses full spec snapshots per version | Exact undo; a deterministic per-edit rng; rejects edits that fail the hard gates. (Its element-keyed mesh cache was never built; stage hand-offs took its place) |
| 35 | Step 16: a reroll is the next version; decor rebuilds from saved stages | Byte-identical to a full build; the gate re-checks only what changed |
| 37 | Step 18: the rest of M4 on the versions | A1 no Session store, the versions are the history; A2 undo/redo on the page; A3 the op vocabulary and the six "not yet supported" ops |

Decision 13 (session security: TTL, LRU, history caps, per-session lock) was mostly dropped with
the Session store by decision 37 A1; loopback bind and CORS stand (Engineering).

## Slice decisions

| Slice | Where |
|---|---|
| Step 16 | [`zone-generator-partial-rebuild/archive.md`](../../../.kiro/specs/zone-generator-partial-rebuild/archive.md) (decision 2: byte-identical; 5: the rest of M4 later) |
| Step 18 | [`zone-generator-edits/archive.md`](../../../.kiro/specs/zone-generator-edits/archive.md) (decision 5: one build per zone; 10: a `rooms_seed` rebuild drops edits) |
