# P-1 Web app and controls — design (living)

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

How the request side works now. Checked against the code at master `c3d9b99` (2026-11-27, the commit that opened the project-docs spec).

## Two ways in, one plan

```
 Describe tab ──► prompt text ──► RulePlanner (or LLMPlanner) ──┐
                                                                ├─► ZonePlan.validate ──► plan_to_spec
 Controls tab ──► control values ─► ZonePlan.from_controls ─────┘
 CLI flags ────► control values ─► ZonePlan.from_controls ─────┘
```

- **Page** ([`web/src/main.ts`](../../../web/src/main.ts), [`controls.ts`](../../../web/src/controls.ts), [`api.ts`](../../../web/src/api.ts)): a Describe | Controls switch
  (remembered per browser, Controls by default) and one Generate. Generate is off on an empty
  description; there is no silent fallback from one mode to the other. The request carries
  `mode` = `prompt` or `controls`; the server records it in the sidecar.
- **Controls** come in six collapsible groups (Zone, Layout, Content, Landscape, Decor, Seeds).
  A control shows only when it applies (zone type, Graph layout, Decor not None, Sites not None);
  controls that don't apply are left out of the request.
- **Server** ([`server/app.py`](../../../server/app.py) `/api/generate`): resolves the mode, checks every field
  (whole numbers, ranges, known values) and answers HTTP 400 naming the field before anything is
  written. `/api/controls` lists rule sets, wall styles, overlays and decor layers;
  `/api/zone_types` (alias `/api/themes`) lists the zone types with any disabled reason.
- **Planner** ([`ai/rule_planner.py`](../../../ai/rule_planner.py)): keyword scoring for zone type, room count, size,
  verticality, locks, theme (Purpose), race, tint, Districts, winding and hall-length words.
  [`ai/llm_planner.py`](../../../ai/llm_planner.py) asks a model for the same `ZonePlan` JSON (`ZONE_PLAN_JSON_SCHEMA`) and
  falls back to the rules without a key.
- **ZonePlan** ([`ai/schema.py`](../../../ai/schema.py)): the contract. `validate` normalises aliases and legacy keys
  (`theme` → `zone_type`, `outdoor` → `wilderness`), clamps, and appends warnings in words
  (for example a prompt-planned zone type that isn't enabled is swapped for `dungeon` with
  `planned_zone_type` kept in the sidecar).

## The vocabulary today

| Axis | Field in code | Values |
|---|---|---|
| Zone type | `zone_type` | `dungeon`, `city`, `wilderness`, `outdoor_dungeon` |
| Purpose | `dungeon_theme` (legacy name) | 11 Purposes plus `cave` ([`generators/semantics.py`](../../../generators/semantics.py)) |
| Race | `dungeon_race` (legacy name) | the race list, with a body height H per race |
| Element | `elemental_tint` (legacy name) | water, lava, ice |
| Room type | `semantic_type` (legacy name) | per-Purpose lists |
| Layout | `layout`, `rule_set` | `classic`, `graph`; `classic_eq`, `warren` |
| Scalars | `winding` (0–2), `hall_length` (0.5–3), `verticality` (flat, moderate, dramatic), `size`, `rooms`, `locks` | |

[Umbrella decision 19](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)'s target names (`purpose`, `builder`, `inhabitants`, `element`, `room_type`, and the
new `condition` axis) are not in the code; read the legacy names through the table above.

## The page beyond the request

- 3D view ([`scene.ts`](../../../web/src/scene.ts)): Z-up camera, first-person walk, WASD suppressed while typing in a field.
- Side panel: metrics, quality banner ([`quality.ts`](../../../web/src/quality.ts)), warnings, version stepper (◂ v2 ▸).
- Files panel ([`artifacts.ts`](../../../web/src/artifacts.ts)), Export row ([`exportrow.ts`](../../../web/src/exportrow.ts)), Feedback box ([`feedback.ts`](../../../web/src/feedback.ts)),
  room view ([`roomview.ts`](../../../web/src/roomview.ts)), Socket markers ([`sockets.ts`](../../../web/src/sockets.ts)): see P-3, P-4, P-5, P-6.
- Build identity: `/api/version` gives the server's commit and a source fingerprint; the page
  shows `server <hash> · web <hash>` and a banner when they disagree or the server is stale.
  The server runs without auto-reload, so it serves the code it started with.

## CLI

`main.py generate` takes `--zone-type` (alias `--theme`), `--rooms`, `--size`, `--verticality`,
`--locks`, `--seed`, `--edges`, `--trees`, `--sites`, `--inhabitant`, `--layout`, `--rule-set`,
`--walls`, `--features`, `--overlay`, `--decor`, `--decor-seed`, `--decor-layer`,
`--rooms-seed`, `--districts`, `--district-theme`, `--district-relationship`, `--no-validate`.
It goes through `ZonePlan.from_controls` and the same pipeline. It has no flags for theme, race,
tint, winding or hall length. `main.py --edit` is covered in P-6, and `main.py export` in P-3.
