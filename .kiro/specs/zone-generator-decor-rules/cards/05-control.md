# 5 — The Decor rules control

Index entry: `tasks.md` task 5. Requirements 2.2, 2.3. **Starts after step 14 task 3 is merged.**

## Goal
A **Decor rules** control in the Controls' Decor group (step 14's layout): "From theme" (no extra layers) plus each layer `/api/controls` lists, with its description as the option's title. It applies (step 14's rule) where Decor applies and Decor is not None, and sends `controls.decor_layers` (a list; empty or absent for "From theme"). `web/src/api.ts` types `decor_layers` on the controls listing and `decor.layers` on the sidecar; the side panel's Props section shows the layers a build used.

## Done when
- [ ] The frontend builds. → verify: `cd web; npx vite build`
- [ ] With "From theme" the body sent is the same as before the task; with a layer chosen it carries `decor_layers` (say in the commit how you checked).
- [ ] `python -m pytest tests/ -q` is green; the Result says it was not checked in the browser by the agent.

## Pitfalls
Build on step 14's visibility predicate; don't add a second mechanism.

## Result
✔ 4a5c1c1 · 3155 passed · frontend builds · not checked in the browser by the agent
