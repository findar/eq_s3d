# 5 — The page

Index entry: `tasks.md` task 5. Requirement 5. Design "Page".

## Goal
`web/src/quality.ts`: the degraded banner, the passed / unknown indicator and the Quality list,
fed from the open version's sidecar for every way a version opens.

## Done when
- [ ] A degraded version shows the banner (count, reason, a link that opens the list) and the
      list out-of-band first; a passing one the indicator; an old version "quality unknown";
      a failed request changes nothing. → verify: a scripted run against the agent's own preview
      servers (8020–8050), with what it saw in the commit body.
- [ ] `cd web; npx vite build` succeeds; `python -m pytest tests/ -q` is green.

## Pitfalls
Leave the user's servers (8000, 5173) and the lead's (8010, 5180) alone. A pinned seed that fails
the bands is the easy way to get a degraded build (task 2's commit body lists failing seeds).
The open Controls cover the top of the 3D view (step 14 follow-up): keep the banner visible.

## Result
