# Design — zone-generator-web-cleanup (roadmap step 14)

Written at master `0b604ea`. Verify against the code: the page may have moved.

## Where things are

- `web/index.html`: the header (`#controls`: brand, `#prompt`, `#generate-description`,
  `#generate-controls`, `#seed`, `#reset-view`, `#show-map`, `<details id="advanced">` holding
  the Controls, `#status`), the canvas, the side panel (`#panel`), the map dialog.
- `web/src/main.ts` (836 lines): `CONTROL_ZONE_TYPES` and `syncControlVisibility` (hide by zone
  type; Graph-only rule set and Scales), `doGenerate(mode)` (builds the request body per mode,
  falls back to Controls on an empty description), the panel fill (`showResult` and kin), the
  zone-type listing from `/api/zone_types`, the Decor listing from `/api/controls`.
- `web/src/style.css` (352 lines): header flex row, `.adv-body` (the Controls), `label {
  display: flex }`, the panel `.row`s.
- `web/src/scene.ts`: overlays (`hasVegetation()` and kin say what the build has).

## Shape

**Header.** `brand · [Describe | Controls] · (description box) · Seed · Generate · Reset View ·
Map · status`. The mode switch is a two-button segmented control (`role="radiogroup"`). In
Describe mode the description box fills the free width; in Controls mode it is hidden and the
Controls show. The Controls stop being a `<details>` that the user opens: in Controls mode they
show as a panel under the header (still collapsible with a chevron, remembered like the mode),
so choosing Controls and seeing the Controls are one act.

**Controls panel.** A CSS grid, `grid-template-columns: max-content 10rem` per group, groups
flowing in columns (`display: grid; grid-auto-flow: column` or a flex-wrap of fixed-width group
cards). Each group is a `<fieldset class="group">` with a `<legend>`. The six groups of Req 3.3.

**Visibility.** One table drives it, extending today's `CONTROL_ZONE_TYPES` to a predicate per
control: `applies(id, state) -> boolean`, where `state` is the zone type and the current values
of Layout, Decor and Sites. `syncControlVisibility` runs on every change of those, hides each
control's label, then hides a group whose controls are all hidden. `readControls` sends only
controls that apply (Req 2.3); today it sends some hidden ones and the server ignores them, so
the server sees no new field and no field it reads changes: bytes stay.

**Side panel.** `showResult` already knows the sidecar: each section gets an `applies(sidecar)`
check; an empty-state block replaces the dashes before the first build. Overlay toggles are
shown from what `scene.ts` loaded (it already answers `hasVegetation()`; add the same for gates,
regions and lights if missing).

**Remembering.** `localStorage` keys `eq_s3d.mode` and `eq_s3d.controlsOpen`, every read and
write in try/catch (the page works without storage).

## Questions decided (see `archive.md` "Decisions")

1. **One Generate button with a mode switch, or keep two buttons and hide one?** *Recommended:
   one button and a switch*: the switch says what will be sent and keeps the header short.
2. **Default mode with nothing remembered?** *Recommended: Controls* (the user: the text
   generator is "less used recently").
3. **Empty description in Describe mode?** *Recommended: Generate disabled* rather than today's
   silent fallback to the Controls, which would surprise now that the Controls are off screen.
4. **Hide or disable controls that don't apply?** *Recommended: hide* (the user: "only show
   controls when they can be used"); disabled zone types stay visible with their reason, since
   those are about the server, not the choice.

## Verification

The page has no test harness (`@types/three` and a type check are deferred). Each task proves
`cd web; npx vite build` and the full Python suite (a server-staleness test and the route tests
cover the request bodies). What the page looks like is checked by the lead in the browser pane
at desktop width (1280) and at a narrow width (900), and by the user at the first look.
