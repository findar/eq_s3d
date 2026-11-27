# 18 — Map layers: show and hide Districts, races, links and the rest

Index entry: `tasks.md` task 18. Requirement 10.

## Goal
The user, at the step 31 look: "it's a little hard to tell what race is in a designated area so being able to toggle tags would be useful in the map interface. so hide/show districts, hide/show races. consider what would be useful to hide and show. also consider that when we actually export the map in an EQ usable format we won't include as much rich information, just basic layouts".

The top-down map (`generators/mapview.py`, shown in the viewer's map modal) gets named layers the modal can show and hide. The rich layers are viewer-only; the EQ map export (`generators/eqmap.py`, the in-client `maps/*.txt`: lines and a few labels) is unchanged, and the modal can show just what that export carries.

## Layers (the lead's pick; adjust if the code argues otherwise)
- **Districts:** hull fill and the District label (Purpose).
- **Races:** each room tagged or tinted by `semantics.room_race`, a race key in the legend; links tagged by `corridor_race`.
- **Links between Districts:** Threshold, breaches, drops (the orange triangles, with height in u) and returns, marked apart from ordinary corridors.
- **Mixed rooms:** host rooms with intruder decor (`district_spill`).
- **Gates and pacing:** lock/key and pacing roles (advisory).
- **Props and sites**, **room IDs**: as today, each its own layer.
- **Walls/outline and corridors**: the base, always on.
- **EQ export view:** a one-click preset showing only what the EQ map file carries (outline lines by depth band, Entrance/Boss labels), so the user sees the in-game map.

## Done when
- [ ] Each layer is one `<g>` with a stable id/class in the SVG; the modal's checkboxes toggle them without a rebuild; choices persist per viewer (localStorage, wrapped in try/catch); defaults show Districts, Races, Links and Room IDs.
- [ ] Races layer: on task 11's case p (prompt seed 2020) every room shows its race; a zone with no District race shows no race layer toggle.
- [ ] The EQ export view matches the `.txt` export's content for one build (compare by `scripts/eqmap_preview.py` or the parser in `generators/eqmap.py`).
- [ ] The downloaded SVG/PNG carries the layers as shown.
- [ ] `eqmap.py` output byte-identical; map tests pass; quick tier; frontend build `cd web && npx vite build`.
- [ ] Screenshot of the modal on case p in the commit body description (what was checked in the browser), and what wasn't.

## Pitfalls
- WASD must not fly the camera while a modal checkbox has focus (lessons-learned, web viewer).
- Keep the map's legend readable as layers hide (only list what's shown).

## Result
