# 3 — Controls, server and planner words

Index entry: `tasks.md` task 3. Requirement 5. Design "Controls and words".

## Goal
The user sets Winding with a slider or with words in the prompt.

## Done when
- [x] `/api/generate` with `plan.winding` 0 and 2 builds zones whose spec records it; a bad value
      falls back to 1. → verify: `python -m pytest tests/test_winding_words.py -q`
- [x] The rule planner maps straight and twisting words as the design says; Controls win. Same
      command.
- [x] The slider shows for dungeon, city and outdoor_dungeon only, is sent only when shown, is in
      the summary, and WASD doesn't move the camera while it has focus. Checked on an agent server
      (8020–8050) in the browser; `cd web; npx vite build` passes.
- [x] `python -m pytest tests/ -q -m "not slow" -n 4` is green.

## Pitfalls
- lessons-learned "Movement keys must be suppressed while typing".
- Don't touch ports 8000/5173 (the user's) or 8010/5180 (the lead's).

## Result
✔ 8b55240 · 3149 passed (not-slow, 6 skipped)
