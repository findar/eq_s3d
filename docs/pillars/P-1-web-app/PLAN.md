# P-1 Web app and controls — plan

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary); IDs follow
[`docs/STYLE.md`](../../STYLE.md).

## Goal

The browser is the main way to make a zone. A user either describes it in words or sets the
controls, and always knows which one produced the zone. Every parameter the plan understands is
a control, normalised the same way whichever path set it.

## Scope

- The page ([`web/`](../../../web)): the Describe | Controls switch, one Generate button, the Controls groups,
  the 3D view, the side panel, the version stepper, and warnings in words.
- The planner surface ([`ai/planner.py`](../../../ai/planner.py), [`ai/rule_planner.py`](../../../ai/rule_planner.py), [`ai/llm_planner.py`](../../../ai/llm_planner.py),
  [`ai/schema.py`](../../../ai/schema.py)): words and controls become one `ZonePlan`.
- The CLI ([`main.py`](../../../main.py)), the secondary surface.
- The zone vocabulary ([umbrella decision 19](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)): field names and value lists.

## Non-goals

- What the zone looks like (P-5) or how it's laid out (P-7). This pillar exposes their levers.
- The map and file downloads (P-4), edits and versions (P-6), and export (P-3).
- Sign-in or many users: the server is local-only (P-9, [ZG-Req-30](../../../.kiro/specs/zone-generator/requirements.md#requirement-30-local-server-security-and-session-limits)).

## Requirements

| ID | Requirement | Parent | Status now |
|---|---|---|---|
| <a id="p-1-req-1"></a>P-1-Req-1 | Two explicit ways to generate, by description and by controls, each producing the zone it says | [ZG-Req-1](../../../.kiro/specs/zone-generator/requirements.md#requirement-1-explicit-generation-modes) | Built in [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 5. [Step 14](../../../.kiro/specs/zone-generator-web-cleanup/tasks.md) turned the two buttons into a Describe / Controls switch with one Generate and no silent fallback |
| <a id="p-1-req-2"></a>P-1-Req-2 | Every plan parameter is a control, and every plan is normalised the same predictable way | [ZG-Req-2](../../../.kiro/specs/zone-generator/requirements.md#requirement-2-control-coverage-and-plan-normalisation) | Mostly built: `ZonePlan.from_controls` feeds into `validate`. Gaps: the CLI has no theme, race, winding or hall-length flags ([P-1-8](OPEN.md#p-1-8)), and the rule-set, theme and race lists are hard-coded in [`web/index.html`](../../../web/index.html) ([P-1-4](OPEN.md#p-1-4)) |
| <a id="p-1-req-3"></a>P-1-Req-3 | Only zone types that pass the gate are offered | [ZG-Req-3](../../../.kiro/specs/zone-generator/requirements.md#requirement-3-zone-type-availability) | Built: the server route `/api/zone_types`. All four types have been enabled since steps [1](../../../.kiro/specs/zone-generator-wilderness/tasks.md) and [5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md) |

Also binding, though it is a design decision rather than a requirement: [umbrella decision 19](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision),
the zone vocabulary (one field per axis, closed value lists). It is half built. The rename of
`theme` to `zone_type` landed in [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md). The content renames (`purpose`, `builder`, `inhabitants`,
`element`, `room_type`, and a new `condition` axis) never landed ([P-1-15](OPEN.md#p-1-15)).

## Traceability

Which slices served each requirement. ([`scripts/task_status.py`](../../../scripts/task_status.py)
will generate this table after [project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md).)

| Requirement | Served by |
|---|---|
| [P-1-Req-1](#p-1-req-1) | [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) (wave 5), [step 14](../../../.kiro/specs/zone-generator-web-cleanup/tasks.md) |
| [P-1-Req-2](#p-1-req-2) | [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) (wave 5), steps [26](../../../.kiro/specs/zone-generator-winding-control/tasks.md), [30](../../../.kiro/specs/zone-generator-hall-length/tasks.md) and [31](../../../.kiro/specs/zone-generator-district-races/tasks.md) (new sliders and controls) |
| [P-1-Req-3](#p-1-req-3) | [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) (wave 4), steps [1](../../../.kiro/specs/zone-generator-wilderness/tasks.md) and [5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md) (enabling `wilderness` and `outdoor_dungeon`) |

## Slices

A slice is one roadmap step (one spec). This pillar's own slices come first, then slices filed
under another pillar that also served this one.

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Phase "web" (pre-spec, [Web app](../../../ROADMAP.md#web-app)) | — | done | (before specs) | FastAPI and Three.js app: generate, first-person walk, overlays, seed input |
| Phase 3 (pre-spec, [Prompt-driven generation](../../../ROADMAP.md#prompt-driven-generation)) | — | done | (before specs) | The rule planner (no API) and the LLM drop-in |
| [step 14](../../../.kiro/specs/zone-generator-web-cleanup/tasks.md) | [`zone-generator-web-cleanup`](../../../.kiro/specs/zone-generator-web-cleanup/tasks.md) | done 2026-11-14 | 11 | Only the controls that apply; six aligned groups; the Describe / Controls switch |

Also served by: [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) (waves 2 and 5: the `zone_type` rename, the two modes, `from_controls`, the
Controls panel; filed under P-2), [step 19](../../../.kiro/specs/zone-generator-quality/tasks.md) (the quality banner; P-7), [step 26](../../../.kiro/specs/zone-generator-winding-control/tasks.md) (the Winding slider;
P-5), [step 30](../../../.kiro/specs/zone-generator-hall-length/tasks.md) (the Hall length slider; P-7), [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) (the District race and intrusion controls;
P-7).

## Next candidates

From this pillar's [`OPEN.md`](OPEN.md): a stale-code banner that can be dismissed ([P-1-1](OPEN.md#p-1-1)),
controls listed by the server instead of hard-coded ([P-1-4](OPEN.md#p-1-4)), the CLI catching up with the page
([P-1-8](OPEN.md#p-1-8)), and the content vocabulary renames ([P-1-15](OPEN.md#p-1-15)). The renames need the user's call on
whether they are still wanted.
