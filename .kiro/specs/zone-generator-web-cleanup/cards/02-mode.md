# 2 — Describe or Controls, one Generate

Index entry: `tasks.md` task 2. Requirement 1. Design "Shape", "Remembering"; decisions 1–3.

## Goal
Replace the two Generate buttons with a Describe | Controls switch (`role="radiogroup"`) and one Generate button. Describe shows the description box and hides the Controls; Controls hides the box and shows the Controls panel under the header (collapsible, its open state remembered). Generate is disabled in Describe mode while the box is empty; Enter in the box still generates. Remember the mode in `localStorage` (try/catch on every access), default Controls. The seed box shows in both modes.

## Done when
- [ ] The frontend builds. → verify: `cd web; npx vite build`
- [ ] The bodies sent are the same as before for a description (`mode: "prompt"`) and for the Controls (`mode: "controls"`), checked as task 1 did.
- [ ] `python -m pytest tests/ -q` is green; the Result says it was not checked in the browser by the agent.

## Pitfalls
The side panel's Plan "Mode" row must still say which mode built the zone. Storage can throw (private windows): the page must work without it. The reroll buttons rebuild in the mode that built the shown zone: keep that.

## Result
✔ 0bfdb20 · 3106 passed · frontend builds · not checked in the browser by the agent (the lead looks)
