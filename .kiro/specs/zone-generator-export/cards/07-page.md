# 7 — The Export row in the page

Index entry: `tasks.md` task 7. Requirement 4.2. Design "Server, CLI and page".

## Goal
An Export row in the side panel's files section, for the version on screen:
- the short-name picker (filter on short or long name, installed first, `arena` preselected);
- Spawn cleanup (off);
- the takeover note;
- **Export**, which then lists the bundle and each file.

`web/src/api.ts` types the two routes.

## Done when
- [ ] The frontend builds. → verify: `cd web; npx vite build`
- [ ] A scripted run against a Server on this branch exports the open version to `arena` and gets
      the bundle link (say in the commit how you checked).
- [ ] `python -m pytest tests/ -q` is green; the Result says it was not looked at in the browser
      by the agent beyond that run.

## Pitfalls
Movement keys stay suppressed while typing in the picker. The row shows only when a build is open
(step 14's visibility rule). Exporting takes about a second: show it busy.

## Result
