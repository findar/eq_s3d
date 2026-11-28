# P-A Web app and controls — plan

## Goal

The browser is the main way to make a zone. A user either describes it in words or sets the
controls, and always knows which one produced the zone. Every parameter the plan understands is
a control, normalised the same way whichever path set it.

## Scope

- The page (`web/`): Describe | Controls switch, one Generate, the Controls groups, the 3D view,
  side panel, version stepper, warnings in words.
- The planner surface (`ai/planner.py`, `ai/rule_planner.py`, `ai/llm_planner.py`,
  `ai/schema.py`): words and controls to one `ZonePlan`.
- The CLI (`main.py`) as the secondary surface.
- The zone vocabulary (umbrella decision 19): field names and value lists.

## Non-goals

- What the zone looks like (P-E) or how it's laid out (P-G); this pillar exposes their levers.
- The map and file downloads (P-D), edits and versions (P-F), export (P-C).
- Authentication or multi-user use: the server is local-only (Engineering, Req 30).

## Requirements (umbrella IDs)

| ID | Requirement | Status now |
|---|---|---|
| P-A.1 | Explicit generation modes: description and controls, each producing the zone it says | Built (M1 wave 5); step 14 turned the two buttons into a Describe / Controls switch with one Generate and no silent fallback |
| P-A.2 | Control coverage and plan normalisation: every plan parameter is a control, normalised predictably | Mostly built: `ZonePlan.from_controls` funnels into `validate`; gaps: the CLI has no theme, race, winding or hall-length flags, and the rule-set, theme and race lists are hard-coded in `web/index.html` (OPEN A-4, A-8) |
| P-A.3 | Zone type availability: only zone types that pass the gate are offered | Built: `/api/zone_types`; all four types enabled since steps 1 and 5 |
| P-A.19* | Zone vocabulary (decision 19): one field per axis, closed value lists | Half built: `theme` → `zone_type` landed in M1; the content renames (`purpose`, `builder`, `inhabitants`, `element`, `room_type`, new `condition`) never landed (OPEN A-15) |

\* Decision 19 is a design decision, not a numbered requirement; it is listed here because it is
this pillar's vocabulary.

## Slices

A slice is one roadmap step (one spec). This pillar's own slices, then slices filed under
another pillar that also served this one.

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Phase "web" (pre-spec) | — | done | (pre-spec) | FastAPI + Three.js app: generate, first-person walk, overlays, seed input |
| Phase 3 (pre-spec) | — | done | (pre-spec) | Rule planner (no API) and LLM drop-in |
| 14 | [`zone-generator-web-cleanup`](../../../.kiro/specs/zone-generator-web-cleanup/tasks.md) | done 2026-11-14 | 11 | Only the controls that apply; six aligned groups; Describe / Controls switch |

Also served by: M1 (waves 2 and 5: the `zone_type` rename, modes, `from_controls`, the Controls
panel; filed under P-B), step 19 (the quality banner; P-G), step 26 (Winding slider; P-E),
step 30 (Hall length slider; P-G), step 31 (District race and intrusion controls; P-G).

## Next candidates

From [OPEN.md](OPEN.md): the dismissable stale-code banner (A-1), controls listed from the server
instead of hard-coded (A-4), the CLI catching up with the page (A-8), and the content vocabulary
renames (A-15), which need the user's call on whether they are still wanted.
