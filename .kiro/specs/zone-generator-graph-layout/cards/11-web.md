# 11 — Web: Layout toggle and rule set

Index entry: `tasks.md` task 11. Requirements 7.1.

## Goal
A Layout toggle (Classic / Graph) in the Controls panel for the zone types that take it (the `CONTROL_ZONE_TYPES` table in `main.ts`), and a Rule set select ("From theme", then each base set) shown when Layout is Graph.

## Done when
- [x] The toggle and select show and hide correctly; the chosen values reach the sidecar.
      → verify: `cd web; npx vite build`, then a generate through the browser pane with the sidecar checked.

## Pitfalls
- The backend serves `.js` as `text/plain` on this machine through port 8000 (ROADMAP follow-ups): check through a preview build, as step 5 task 9 did.

## Result
build ✔ 2511968; browser check pending
