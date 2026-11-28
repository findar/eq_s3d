# P-D True-layout artifacts — decisions

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| 5 | The EQ map convention is grounded, not assumed | A test against real zones and their `maps/*.txt` pins it |
| 6 | The outline is extracted once from the TER | It feeds both the EQ map and the SVG; schematic annotations stay on top; maps only for the accepted build |
| 21 | M2 refinements at the step 1b close | (a) the boundary is the geometric Floor_Boundary; (b) negate + swap scored over 8 candidates at 5 u, collinear merge at 0.02 u, one Main band when not stacked, ledges in band colour; (c) the in-client check moves to Export (P-C) |

## Slice decisions

| Slice | Where |
|---|---|
| Step 1b | [`zone-generator-m2-true-layout-artifacts/archive.md`](../../../.kiro/specs/zone-generator-m2-true-layout-artifacts/archive.md), its `design.md` "As-built verification" |
| Step 31 (map layers) | [`zone-generator-district-races/archive.md`](../../../.kiro/specs/zone-generator-district-races/archive.md) (umbrella decision 48 A4) |

## Settled

- The in-game map export stays lines and labels only (decision 48 A4).
