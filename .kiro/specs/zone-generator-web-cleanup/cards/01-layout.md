# 1 — Grouped, aligned Controls and header

Index entry: `tasks.md` task 1. Requirement 3. Design "Shape".

## Goal
Regroup the Controls into the six groups of Req 3.3 (`<fieldset class="group">` with a legend each), laid out as label/control grids with one control width per column, and line up the header on one row at 1280 px (one height and baseline, whole-group wrapping when narrower). Line the side panel's values up to one right edge with the seed buttons in their own column, and give buttons one style per role with no two-line button text. Keep every control's element id, so `main.ts` reads them as before; have `syncControlVisibility` also hide a group whose controls are all hidden.

## Done when
- [ ] The frontend builds. → verify: `cd web; npx vite build`
- [ ] No request body changes: for each zone type, the body `doGenerate` sends is the same as before the task (say in the commit how you checked, e.g. logging the body for each zone type before and after).
- [ ] `python -m pytest tests/ -q` is green; the Result says it was not checked in the browser by the agent (the lead looks).

## Pitfalls
Movement keys stay suppressed while typing (lessons-learned "Web viewer"). A commit-message hook blocks two words about the frontend build (lessons-learned "Environment"). `web/node_modules` is shared through a junction: don't change dependencies. The `label { display: flex }` rule fights inline `display` in `syncControlVisibility`: keep hiding working.

## Result
