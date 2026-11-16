# 5 — Versions and Use in zone in the page

Index entry: `tasks.md` task 5. Requirement 5. Design "The page".

## Goal
The header shows the open version (`v3`) with ◂ ▸ through the zone's versions (from
`/api/zones/<zone>/versions`); opening one loads its GLB, sidecar, map and files, keeping the
camera. Reroll decor sends `/api/rebuild {decor_seed}` and Reroll rooms `{rooms_seed}`, each
opening the new version. The room view gains **Use in zone** (enabled when the room's decor seed
differs from the open version's), which sends `{room_decor: {room, decor_seed}}` and reopens the
room on the new version. The side panel shows a Version row (`v3 of 3 · from v2 · decor seed`).
`web/src/api.ts` types the new routes and the sidecar's `version` block.

## Done when
- [ ] The frontend builds. → verify: `cd web; npx vite build`
- [ ] Against a Server on this branch merged with tasks 1 and 2 (or their API mocked), a
      scripted run makes v2 by Reroll decor, steps back to v1 and forward, and the room view's
      Use in zone sends the right body (say in the commit how you checked).
- [ ] `python -m pytest tests/ -q` is green; the Result says it was not checked in the browser
      by the agent beyond that run.

## Pitfalls
Step 14's visibility rule: the version arrows show only when the zone has more than one
version. Movement keys stay suppressed while typing. A rebuild takes seconds: show it busy and
keep the old version on screen until the new one loads.

## Result
