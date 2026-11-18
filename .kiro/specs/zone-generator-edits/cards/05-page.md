# 5 — The Feedback section in the page

Index entry: `tasks.md` task 5. Requirement 4. Design "Page".

## Goal
`web/src/feedback.ts` and its markup: text field, Apply, notes, Undo, Redo, the Affected_Set
highlight, and the Version row naming an edit.

## Done when
- [x] Apply makes and opens the next version; `applied: false` keeps the open one and shows why;
      Undo/Redo follow parent links and disable at the ends. → verify: a scripted run against
      the agent's own preview servers (8020–8050), with what it saw in the commit body.
- [x] Typing in the box never moves the camera. Same run.
- [x] `cd web; npx vite build` succeeds; `python -m pytest tests/ -q` is green.

## Pitfalls
Movement keys must be suppressed while typing (lessons-learned "Web viewer"). Leave the user's
servers (8000, 5173) and the lead's (8010, 5180) alone. A value set by script may not reach
page state (step 17 follow-up): drive the page with real typing.

## Result
✔ 707ae93 · 3516 passed · frontend builds
