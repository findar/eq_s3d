# 7 — The page and the map

Index entry: `tasks.md` task 7. Requirement 6. Design "Page and map".

## Goal
A Districts checkbox in Controls (dungeon only) sent with generate and ticked from a sidecar plan
that has it; District hulls and heavier Threshold corridors on the map with a District legend; the
room panel naming the room's District and Purpose.

## Done when
- [x] A scripted run against the agent's own preview servers (8020–8050): tick Districts, generate
      a 16-room dungeon; the map shows 2–3 hulls and the legend names their Purposes; a room's panel
      names its District; a prompt "a temple fallen to the dead" shows the box ticked. What it saw
      goes in the commit body.
- [x] `python -m pytest tests/test_properties_mapview.py -q` passes (hulls drawn after the outline,
      umbrella 14.1's order).
- [x] `cd web; npx vite build` succeeds; `python -m pytest tests/ -q` is green.

## Pitfalls
Leave the user's servers (8000, 5173) and the lead's (8010, 5180) alone. The open Controls cover
the top of the 3D view (step 14 follow-up). Never write "Vite" or "dev server" in a commit message.

## Result
✔ fee1c5c · 3716 passed · frontend builds
