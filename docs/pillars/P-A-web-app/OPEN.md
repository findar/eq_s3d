# P-A Web app and controls — open items

Status: **open** (to do), **parked** (known, deliberately left), **waiting** (on the user's word
or eyes), **in flight** (an active step covers it). Checked: **code** (confirmed in the code at
`c3d9b99`), **record** (needs a build, a sweep or a look to re-check; carried as recorded).
Roll-up: [OPEN.md](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| A-1 | The stale-code banner covers the Controls and can't be dismissed; it fires on any HEAD move, so a docs-only merge flags the server stale (consider keying it on `source_fingerprint`) | ROADMAP Known issues (user, step 25 look) | open | code: `web/src/main.ts` ~126, no dismiss |
| A-2 | The open Controls cover the top of the 3D view | step 14 archive | open | record |
| A-3 | Hidden controls still sent (decor seed with Decor None, Inhabitants with Sites none): same build, but the sidecar records the value | step 14 archive | parked (by design) | record |
| A-4 | Rule set, Theme and Race selects are hard-coded in `web/index.html`; a new rule-set file needs a page edit (`/api/controls` exists but the page doesn't read the lists from it) | step 6 archive | open | code: `web/index.html` 134–188 |
| A-5 | The Decor tooltip still says "in the rooms"; Sites take decor too | step 11 archive | open | code: `web/index.html` 275 |
| A-6 | Control values set by script don't reach the page's state | step 17 archive | open | record |
| A-7 | WASD while the Hall length slider has focus: not checked | step 30 archive | open | record |
| A-8 | The CLI lags the page: no theme, race, tint, winding or hall-length flags (`--theme` is the old alias for `--zone-type`) | step 6 archive; winding and hall length found here | open | code: `main.py` 416–493 |
| A-9 | Prompt words don't choose a layout or rule set ("maze", "linear" only change the room count) | step 6 archive (umbrella Req 22.5–22.7) | open | code: `ai/rule_planner.py` 114 |
| A-10 | A race with no theme builds fortress rooms; the Theme select's "None" reads as "no theme" | step 6 archive | open | record |
| A-11 | Districts are numbered from 1 on the page and 0 in warnings; Purposes shown raw (`corrupted_sanctum`) | step 20 archive | open | code: `web/src/api.ts` 270 |
| A-12 | Pre-existing `tsc` errors; `@types/three` and a frontend type check deferred | step 17 archive; ROADMAP | parked (user deferred) | code: `web/package.json` has no `@types/three` |
| A-13 | The backend serves `.js` as `text/plain` on this Windows machine when the app is opened through port 8000 | ROADMAP | open | code: no MIME override in `server/app.py` |
| A-14 | The web bundle is one ~570 kB chunk (build warns over 500 kB) | ROADMAP Known issues | parked (cosmetic) | record |
| A-15 | Decision 19's content renames never landed: `dungeon_theme`, `dungeon_race`, `elemental_tint`, `semantic_type` are still the field names; there is no `condition` axis | found by this proposal | waiting (still wanted?) | code: `generators/zone_spec.py` 383–385 |
| A-16 | The server doesn't auto-reload; restart after pulling (the banner covers it) | ROADMAP Known issues | parked (by design) | code |
| A-17 | A thorough failure in `test_cave_words_mean_dungeon`: "cave outdoor dungeon" plans an outdoor dungeon where the test expects word counts to pick `dungeon` | step 19 archive | open | record |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| `ZONE_PLAN_JSON_SCHEMA` lacks `winding` and `hall_length` (steps 26, 30) | `2e325f3` (step 31 task 9) |
| The prompt silently overrides the controls (umbrella Known Limitation 7) | M1 wave 5, merge `17a4d1c`; step 14 |
| The CLI is controls-only and lacks locks (umbrella Known Limitation 6) | M1 wave 5, merge `17a4d1c` |
