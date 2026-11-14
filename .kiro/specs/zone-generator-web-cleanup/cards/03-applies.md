# 3 — Show only what applies

Index entry: `tasks.md` task 3. Requirement 2. Design "Visibility", "Side panel"; decision 4.

## Goal
Turn `CONTROL_ZONE_TYPES` into a predicate per control over the zone type, Layout, Decor and Sites (Req 2.1), run it on every change of those, hide each control that doesn't apply and any group left empty, and send only controls that apply (Req 2.3). In the side panel, show a section, row, reroll button or overlay toggle only when the shown build has it (Req 2.4, 2.5), with a "No zone yet" state before the first build (Req 2.6). Add `scene.ts` checks for gates, regions and lights if they're missing.

## Done when
- [ ] The frontend builds. → verify: `cd web; npx vite build`
- [ ] For each zone type, the body sent holds exactly the controls that apply, and the server builds each the same as before: the same zone for the same seed (say in the commit how you checked, e.g. `POST /api/generate` per zone type before and after, comparing the `.eqg` less its 4-byte footer).
- [ ] `python -m pytest tests/ -q` is green; the Result says it was not checked in the browser by the agent.

## Pitfalls
Don't drop a control the server reads: compare with `server/app.py`'s request model and `ai/expand.py` before hiding one. A value that defaults on the server (e.g. Decor) must give the same build whether sent or left out; if not, keep sending it and say so in the commit.

## Result
