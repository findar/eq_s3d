# P-8 World — decisions

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Umbrella decision numbers link to the umbrella design's
[Decisions Made in This Revision](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| [32](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) builds a zone as stages off World Sockets | World → Attach → Build → Decor → Pack; versioned JSON hand-offs that the server never reads back; a seed per stage; reroll only the stage to blame; the seams that [M4](../../../.kiro/specs/zone-generator/design.md#delivery-plan)'s partial rebuild needed |

## Slice decisions

| Slice | Where |
|---|---|
| [Step 12](../../../.kiro/specs/zone-generator-world-sockets/tasks.md) | [`zone-generator-world-sockets/archive.md`](../../../.kiro/specs/zone-generator-world-sockets/archive.md) "Decisions" ([step 12 decision 5](../../../.kiro/specs/zone-generator-world-sockets/archive.md#decisions): stage blame), and its design questions 1 (an exact Mouth, several dungeons) and 3 (the `door` kind) |
| [Step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md) | [`zone-generator-site-sockets/archive.md`](../../../.kiro/specs/zone-generator-site-sockets/archive.md) (World version 2) |

## Waiting

- The multi-zone design itself: the user reviews it before anything is chosen.
