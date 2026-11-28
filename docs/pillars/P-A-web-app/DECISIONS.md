# P-A Web app and controls — decisions

Links, not copies. The umbrella decisions are numbered as in
[`.kiro/specs/zone-generator/design.md`](../../../.kiro/specs/zone-generator/design.md)
"Decisions Made in This Revision".

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| 2 | One expansion path | Controls build a `ZonePlan` (`from_controls`) and go through `plan_to_spec` like prompts; the golden test found 72/72 cases unchanged |
| 19 | Zone vocabulary | One field per descriptive axis with closed value lists; "theme" is only a UI label. The `zone_type` rename landed in M1; the content renames were planned for M3 and did not land |

## Slice decisions

| Slice | Where | Topics |
|---|---|---|
| M1 waves 2 and 5 | [`zone-generator-m1-controls-traversability/design.md`](../../../.kiro/specs/zone-generator-m1-controls-traversability/design.md), its `tasks.md` Decisions | rename boundaries, mode resolution, 400-before-write, controls golden test |
| Step 14 | [`zone-generator-web-cleanup/archive.md`](../../../.kiro/specs/zone-generator-web-cleanup/archive.md) | one Generate, controls that don't apply left out of the request |

## Settled (don't relitigate)

- The prompt never silently overrides the controls (umbrella Known Limitation 7, fixed in M1).
- The target short name is not a generation control; it is chosen at Export (decision 20, P-C).
