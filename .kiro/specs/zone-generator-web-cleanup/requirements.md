# Requirements Document

> **STATUS: roadmap step 14, ready.** Drafted 2026-11-14 at master `0b604ea` from the user's
> request the same day: "i also want to cleanup the web ui. if possible only show controls
> when they can be used, make sure all controls have clean alignment, and since the text
> generator seems to be less used recently we should have a way to show only the text prompt
> or the controls when we generate". The design's open questions were decided on their
> recommendations (`archive.md` "Decisions"). Task index: `tasks.md` (card format).

## Introduction

Roadmap step 14: **web UI cleanup.** The page (`web/`) grew a control at a time over thirteen
steps. Today the header holds the description box, two Generate buttons (from description,
from controls), the seed, Reset View, Map and a collapsed **Controls** panel of about twenty
controls; the side panel lists every section and overlay whether or not the build has them.
Some controls already hide by zone type (`syncControlVisibility` in `web/src/main.ts`), but
not all, and the panel's rows don't line up.

This step makes the page show what applies and nothing else, lines everything up, and lets the
user generate from either the description or the controls with only that one on screen. It
changes the page only: no build, sidecar or server route changes, so every build's bytes stay
as they are.

**Out of step 14:** a frontend type check and `@types/three` (deferred by the user); serving the
theme, race and rule-set lists from the server (a step 6 follow-up); the single-room decor view
(step 15); any change to what a build makes.

## Glossary

- **Generate mode**: Describe (the description box) or Controls (the Controls panel). Only the
  chosen one shows; one Generate button sends it.
- **Applies**: a control applies when, for the zone type and the other choices on screen, the
  server would read it. A side-panel section or overlay applies when the shown build has what
  it shows.

## Requirements

### Requirement 1 — Generate from one mode at a time

**User story:** As a zone author who mostly uses the Controls, I want only the Controls on
screen when I generate from them, and only the description when I describe, so the page isn't
cluttered with the one I'm not using.

1. The header SHALL offer a two-way Generate mode switch, **Describe** and **Controls**, and a
   single **Generate** button that sends the chosen mode (`mode: "prompt"` with the description,
   or `mode: "controls"` with the Controls).
2. In Describe mode the description box SHALL show and the Controls SHALL NOT; in Controls mode
   the Controls SHALL show and the description box SHALL NOT.
3. Enter in the description box SHALL generate in Describe mode, as today.
4. The seed box SHALL show in both modes (both send it).
5. The page SHALL remember the chosen mode for that browser (a per-viewer convenience); with
   nothing remembered it SHALL start in **Controls** mode.
6. An empty description in Describe mode SHALL NOT silently build from the Controls: Generate
   SHALL be disabled until there is text (today it falls back to the Controls).
7. The side panel's Plan section SHALL still say which mode built the shown zone.

### Requirement 2 — Show a control only when it can be used

**User story:** As a zone author, I want to see only the controls that do something for what
I've chosen, so I don't set one the server will ignore.

1. Each control in the Controls SHALL show only when it applies, by zone type and by the other
   controls that gate it: the rule set, Finish, Structure, Clutter and Overlay under the Graph
   layout only; the decor seed only when Decor is not None; Inhabitants only when Sites is not
   None; the Landscape group only for wilderness and outdoor dungeons; and the existing
   zone-type rules for the rest (`CONTROL_ZONE_TYPES`).
2. A zone type the server lists as disabled SHALL stay visible but unselectable with its reason,
   as today.
3. Hidden controls SHALL NOT be sent (the server ignores them anyway; the body stays as small as
   what applies).
4. In the side panel, a section SHALL show only when the shown build has something for it:
   Seeds' decor row and **reroll decor** only when the build has Decor; Props only when it
   placed Props; Pacing, Content and Gates rows only when the build has them.
5. An overlay toggle SHALL show only when the shown build has what it toggles (Trees with trees,
   Gates with gates, Regions with regions, Lights with lights); Wireframe and Room IDs always.
6. Before any build, the side panel SHALL show only the build line and a short "No zone yet"
   note, not a column of dashes.

### Requirement 3 — Clean alignment

**User story:** As a zone author, I want the controls and panels lined up, so the page reads
as one tool.

1. The header SHALL sit on one row at 1280 px wide and wider, its controls sharing one height
   and baseline; narrower, it SHALL wrap by whole groups, never mid-control.
2. The Controls SHALL lay out as a grid of label and control pairs: labels in one column, right
   or left aligned consistently, controls in the next, every select and number box the same
   width within a column.
3. Related controls SHALL sit together under a small heading: **Zone** (type, rooms, size,
   verticality, locks), **Layout** (layout, rule set, Finish, Structure, Clutter, Overlay),
   **Content** (theme, race), **Landscape** (edges, trees, Sites, Inhabitants), **Decor**
   (Decor, decor seed) and **Seeds** (rooms seed). A group with nothing showing SHALL hide.
4. The side panel's rows SHALL align their values to one right edge, with the seed buttons
   lined up in their own column.
5. Buttons SHALL share one style per role (primary: Generate; secondary: the rest), with no
   button text wrapping onto two lines at 1280 px.

### Requirement 4 — Nothing else changes

1. No server route, request field, sidecar field or build output SHALL change.
2. The keyboard SHALL work as today: movement keys ignored while typing, R resets the view, M
   opens the map, Esc closes it.
3. The stale-code banner, the build line, the warnings, the Files list, the map dialog and its
   Socket markers SHALL work as today.
4. `cd web; npx vite build` SHALL succeed, and the full Python suite SHALL stay green.
