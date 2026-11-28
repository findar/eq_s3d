# P-1 Web app and controls — open items

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

IDs are `P-1-<k>` ([`docs/STYLE.md`](../../STYLE.md)). The other pillars' `OPEN.md` files use
the same columns. Roll-up of every pillar: [`OPEN.md`](../../../OPEN.md).

- **Status**: **open** (to do), **parked** (known, deliberately left), **waiting** (on the user's
  word or eyes), **in flight** (an active step covers it).
- **Source**: where the item was first recorded. "Step N archive" is that step's `archive.md`
  "Follow-ups"; "gap 2026-11-27" is one of the gaps listed in
  [project-docs requirement 3](../../../.kiro/specs/project-docs/requirements.md#requirements);
  "found by [project-docs task 1](../../../.kiro/specs/project-docs/cards/01-proposal.md)" means the pillar proposal found it while checking the code.
- **Checked**: **code** means confirmed in the code at master `c3d9b99` (2026-11-27, the commit
  that opened the project-docs spec); **record** means it needs a build, a sweep or a look to
  re-check, so it is carried as recorded.

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-1-1"></a>P-1-1 | The stale-code banner covers the Controls and can't be dismissed; it fires whenever the checked-out commit changes, so a docs-only merge flags the server as stale (consider keying it on `source_fingerprint`) | [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) (raised by the user at the [step 25](../../../.kiro/specs/zone-generator-winding-routes/tasks.md) look) | open | code: [`web/src/main.ts`](../../../web/src/main.ts) ~126, no dismiss |
| <a id="p-1-2"></a>P-1-2 | The open Controls cover the top of the 3D view | [step 14 archive](../../../.kiro/specs/zone-generator-web-cleanup/archive.md) | open | record |
| <a id="p-1-3"></a>P-1-3 | Hidden controls still sent (decor seed with Decor None, Inhabitants with Sites none): same build, but the sidecar records the value | [step 14 archive](../../../.kiro/specs/zone-generator-web-cleanup/archive.md) | parked (by design) | record |
| <a id="p-1-4"></a>P-1-4 | Rule set, Theme and Race selects are hard-coded in [`web/index.html`](../../../web/index.html); a new rule-set file needs a page edit (`/api/controls` exists but the page doesn't read the lists from it) | [step 6 archive](../../../.kiro/specs/zone-generator-graph-layout/archive.md) | open | code: [`web/index.html`](../../../web/index.html) 134–188 |
| <a id="p-1-5"></a>P-1-5 | The Decor tooltip still says "in the rooms"; Sites take decor too | [step 11 archive](../../../.kiro/specs/zone-generator-room-decor/archive.md) | open | code: [`web/index.html`](../../../web/index.html) 275 |
| <a id="p-1-6"></a>P-1-6 | Control values set by script don't reach the page's state | [step 17 archive](../../../.kiro/specs/zone-generator-export/archive.md) | open | record |
| <a id="p-1-7"></a>P-1-7 | WASD while the Hall length slider has focus: not checked | [step 30 archive](../../../.kiro/specs/zone-generator-hall-length/archive.md) | open | record |
| <a id="p-1-8"></a>P-1-8 | The CLI lags the page: no theme, race, tint, winding or hall-length flags (`--theme` is the old alias for `--zone-type`) | [step 6 archive](../../../.kiro/specs/zone-generator-graph-layout/archive.md); winding and hall length found by [project-docs task 1](../../../.kiro/specs/project-docs/cards/01-proposal.md) | open | code: [`main.py`](../../../main.py) 416–493 |
| <a id="p-1-9"></a>P-1-9 | Prompt words don't choose a layout or rule set ("maze", "linear" only change the room count) | [step 6 archive](../../../.kiro/specs/zone-generator-graph-layout/archive.md) ([ZG-Req-22](../../../.kiro/specs/zone-generator/requirements.md#requirement-22-topology-control)) | open | code: [`ai/rule_planner.py`](../../../ai/rule_planner.py) 114 |
| <a id="p-1-10"></a>P-1-10 | A race with no theme builds fortress rooms; the Theme select's "None" reads as "no theme" | [step 6 archive](../../../.kiro/specs/zone-generator-graph-layout/archive.md) | open | record |
| <a id="p-1-11"></a>P-1-11 | Districts are numbered from 1 on the page and 0 in warnings; Purposes shown raw (`corrupted_sanctum`) | [step 20 archive](../../../.kiro/specs/zone-generator-districts/archive.md) | open | code: [`web/src/api.ts`](../../../web/src/api.ts) 270 |
| <a id="p-1-12"></a>P-1-12 | The TypeScript compiler (`tsc`) reports errors that predate [step 17](../../../.kiro/specs/zone-generator-export/tasks.md); adding `@types/three` and a frontend type check is deferred | [step 17 archive](../../../.kiro/specs/zone-generator-export/archive.md); [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) | parked (user deferred) | code: [`web/package.json`](../../../web/package.json) has no `@types/three` |
| <a id="p-1-13"></a>P-1-13 | The backend serves `.js` as `text/plain` on this Windows machine when the app is opened through port 8000 | [ROADMAP](../../../ROADMAP.md) | open | code: no MIME override in [`server/app.py`](../../../server/app.py) |
| <a id="p-1-14"></a>P-1-14 | The web bundle is one ~570 kB chunk (build warns over 500 kB) | [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) | parked (cosmetic) | record |
| <a id="p-1-15"></a>P-1-15 | [Umbrella decision 19](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)'s content renames never landed: `dungeon_theme`, `dungeon_race`, `elemental_tint`, `semantic_type` are still the field names; there is no `condition` axis | found by [project-docs task 1](../../../.kiro/specs/project-docs/cards/01-proposal.md) | waiting (still wanted?) | code: [`generators/zone_spec.py`](../../../generators/zone_spec.py) 383–385 |
| <a id="p-1-16"></a>P-1-16 | The server doesn't auto-reload; restart after pulling (the banner covers it) | [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) | parked (by design) | code |
| <a id="p-1-17"></a>P-1-17 | A thorough failure in `test_cave_words_mean_dungeon`: "cave outdoor dungeon" plans an outdoor dungeon where the test expects word counts to pick `dungeon` | [step 19 archive](../../../.kiro/specs/zone-generator-quality/archive.md) | open | record |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| `ZONE_PLAN_JSON_SCHEMA` lacks `winding` and `hall_length` (steps [26](../../../.kiro/specs/zone-generator-winding-control/tasks.md), [30](../../../.kiro/specs/zone-generator-hall-length/tasks.md)) | `2e325f3` ([step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) task 9: District race and intrusion controls, and the matching LLM schema fields) |
| The prompt silently overrides the controls ([umbrella Known Limitation 7](../../../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them)) | merge `17a4d1c` ([M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 5: explicit modes and `from_controls`); [step 14](../../../.kiro/specs/zone-generator-web-cleanup/tasks.md) |
| The CLI is controls-only and lacks locks ([umbrella Known Limitation 6](../../../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them)) | merge `17a4d1c` ([M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 5: the CLI goes through `from_controls`) |
