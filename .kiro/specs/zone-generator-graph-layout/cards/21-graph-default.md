# 21 — Graph becomes the default layout

Index entry: `tasks.md` task 21. Requirements 7.1, 7.3 (amended). Added from the acceptance pass.

## Goal
The user decided at task 16 (2026-11-04): "graph should be the default going forward". New `dungeon` and `outdoor_dungeon` requests — Controls panel, description box, CLI, server — build with the graph engine unless Classic is asked for. Classic stays selectable everywhere.

## Done when
- [x] A new request with no layout builds Graph for `dungeon` and `outdoor_dungeon`, through every entry point: the Controls panel (the toggle shows Graph first), the description box (the planner's plan), `python main.py generate` with no `--layout`, and the server's controls and prompt modes. Other zone types are untouched.
- [x] A plan saved before step 6 (no `layout` field, e.g. an old sidecar's plan or a reproduce request) still rebuilds as Classic, byte-identical: only new requests default to Graph. The rule is written where the plan is loaded, with the reason.
- [x] Every test, golden and acceptance case that relied on Classic being the default says `classic` explicitly and still checks what it checked; `docs/ACCEPTANCE.md`'s earlier sections (steps 1–5) still describe what their cases build (add "Layout: Classic" where a case's checks depend on it, or re-verify it on Graph), and step 6's section says Graph is the default.
- [x] Task 2's classic goldens pass unchanged (with an explicit classic layout).
      → verify: `python -m pytest tests/ -q`, `cd web; npx vite build`, and a generate through the browser pane (the lead checks it).
- [x] The requirements' Req 7.1 says Graph is the default (one line; the close records decision 26).

## Pitfalls
- Reproducibility: a pinned seed with no layout must not silently change between versions for an old saved plan. Separate "new request default" from "legacy plan without the field".
- The pipeline's time budgets and gate sweeps that build defaults now build Graph: check the timings still hold.
- Frontend-only changes never run the Python suite (task 11 broke hygiene that way): run it.

## Result
✔ 4f6a48a · 1225 passed; browser check ✔ (Graph first on load, description box builds Graph, Classic selectable)
