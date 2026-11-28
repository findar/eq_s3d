# P-4 True-layout artifacts — decisions

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Umbrella decision numbers link to the umbrella design's
[Decisions Made in This Revision](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| [5](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | The EQ map convention is grounded, not assumed | A test against real zones and their `maps/*.txt` pins it |
| [6](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | The outline is extracted once from the TER | It feeds both the EQ map and the SVG; schematic annotations stay on top; maps only for the accepted build |
| [21](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [M2](../../../.kiro/specs/zone-generator/design.md#delivery-plan) refinements at the [step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md) close | (a) the floor's edge is found geometrically; (b) the "negate and swap" convention won against all 8 sign and swap candidates within 5 u, lines in a row merge within 0.02 u, a zone with no stacked floors has one band, ledges take their band's colour; (c) the in-client check moves to Export (P-3) |

## Slice decisions

| Slice | Where |
|---|---|
| [Step 1b](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md) | [`zone-generator-m2-true-layout-artifacts/archive.md`](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/archive.md), its [`design.md` "As-built verification"](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/design.md#as-built-verification) |
| [Step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) (map layers) | [`zone-generator-district-races/archive.md`](../../../.kiro/specs/zone-generator-district-races/archive.md) ([umbrella decision 48](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part A4) |

## Settled

- The in-game map export stays lines and labels only ([umbrella decision 48](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision), part A4).
