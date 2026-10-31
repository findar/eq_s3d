# 9 — Artifacts panel in the web app

Index entry: `tasks.md` task 9. Design: "Artifacts_Panel", Decision 13.
Requirement 10.

## Goal
A side-panel section that shows the latest build's map and offers its files for
download: the SVG, a PNG rendered in the browser at 2×, each EQ map `.txt`, and
the `.eqg`. An artifact that fails to load is marked unavailable without
breaking the others.

## Done when
- [ ] `web/src/artifacts.ts` provides `showArtifacts`, `loadMapSvg`, `svgToPng`
      and `markUnavailable`; `index.html` has the `#artifacts` section; the map
      modal gains "Download PNG".
- [ ] Every download is a native link with a text label naming the file type,
      saved as `<name>.*` (the PNG as `<name>.map.png`), and reachable by
      keyboard.
- [ ] Each entry is probed with HEAD; a failure marks only that entry.
- [ ] Movement keys don't move the camera while the panel or the dialog has
      focus.
- [ ] The frontend builds.
      → verify: `cd web; npx vite build`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- lessons-learned: "Movement keys must be suppressed while typing".
- There's no frontend test framework (Decision 13); task 12 checks this by hand.
- The commit-message hook blocks two frontend tool words; see lessons-learned.

## Result
