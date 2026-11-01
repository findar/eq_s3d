# Archive — zone-generator-m2-true-layout-artifacts

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Signed off 2026-10-31; master `a97231a`. Suite 580 (fast and thorough).

| Task | What landed |
|------|-------------|
| 1 | `generators/eqmap.py`: Map_Convention negate + swap, grounded on stock maps (tutoriala 1.42 u, bazaar 0.54 u); `.txt` format and parser, all 143 stock maps parse with nothing skipped |
| 2 | Walls beside and above every doorway (`geometry.py`) |
| 3 | `generators/mapgeom.py`: outline extractor and depth bands, proved on synthetic worlds |
| 4 | Outline Properties 1–3 on box builds; ledge share fell from 55–63 % to 7–13 % |
| 5 | Outline layer in the map SVG (`render_map_svg(outline=)`) |
| 6 | EQ map layers from the outline: one colour per band, Entrance/Boss labels |
| 7 | Pipeline post-pass writes the SVG and `maps/<name>*.txt` for accepted builds only; sidecar `map_files` and `outline` block; fallback warnings |
| 8 | Server `maps/` route, HEAD, `artifacts` URLs in the generate response |
| 9 | Web Files panel: SVG, 2× PNG, `.txt`, `.eqg` downloads, HEAD-probed |
| 10 | `scripts/eqmap_preview.py` overlay |
| 11 | Wilderness cases in Properties 3 and 13; ACCEPTANCE "Step 1b — True-layout map"; thorough run green |
| 12 | Human acceptance pass: signed off, no findings |
| 14 | Corridors a full width clear of rooms, walled bends, grade-cap exact fallback (every box layout moved) |
| 15 | Wilderness: every playable cell reachable from spawn |

## Decisions

The design's "Decisions" section (1–13) stands. The user answered its open
questions on 2026-10-30:

- **Open room walls (design Open question 2):** fixed inside step 1b, as task 2
  (walls beside and above every doorway), before the outline is checked on box
  builds. It changes box TER bytes for every seed with a corridor, not the
  layout.
- **In-client `.txt` check (Open question 1):** 1b closes with the grounding
  test plus the overlay script (task 10). The in-client half of the exit
  criterion moves to M6's in-engine smoke load.
- **Wilderness map content (Open question 4):** accepted as the terrain border
  plus slope breaks over 40°. Contour or path lines are a possible later
  requirement, not 1b.
- **Boss label text (Open question 5):** every climax label reads `Boss` until
  M3 adds a name field.
- **Umbrella wording (Open question 3):** the refinements and superseded
  details are recorded in the umbrella spec at the close step (task 13).
- **Corridor clearance (task 14):** rooms sit a full corridor width apart (every
  layout moves); a Z middle leg can't fit the old half-width gap.
