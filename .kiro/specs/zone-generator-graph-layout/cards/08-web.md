# 8 — Web: layout control

Index entry: `tasks.md` task 8. Requirements 6.1.

## Goal
A Layout select in the Controls panel, shown for the zone types that take it (the `CONTROL_ZONE_TYPES` table in `main.ts`), sent with the controls.

## Done when
- [ ] The select shows for the right zone types and is hidden otherwise; the chosen value reaches the sidecar.
      → verify: `cd web; npx vite build`, then a generate through the browser pane with the sidecar checked.

## Pitfalls
- The backend serves `.js` as `text/plain` on this machine through port 8000 (ROADMAP follow-ups): check in the browser through a preview build, as step 5 task 9 did.

## Result
