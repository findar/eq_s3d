# 4 — Room scale from the cave profile

Index entry: `tasks.md` task 4. Requirement 3. Design "Style profile".

## Goal
A `cave` zone (single District, or District 0 `cave`) gets `spec.style_profile = "cave"` and its
layout reads `floor_area` from `styles/cave.json`; every other zone is unchanged.

## Done when
- [ ] Purpose `cave` → `style_profile == "cave"` and smaller mean room area than the same seed as
      `warren` (sizes in the commit body); any other Purpose → today's profile; a saved spec keeps
      its profile on load and rebuild. → verify: `python -m pytest tests/test_cave_profile.py -q`
- [x] The byte check passes; `python -m pytest tests/ -q` is green.

## Pitfalls
`generators/layout.py` is a cross-branch hotspot: touch only the constructor and its one call.
Outdoor dungeons and cities keep their profiles.

## Result
✔ 9c86fbe · 3755 passed, 4 expected (2 texture_recipes, district_purposes three_districts, room_context corpus); 'smaller than warren' does not hold (cave Room_Types outweigh the profile), box 1 left for the lead
