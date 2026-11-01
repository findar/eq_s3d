# 5 — Web renders the textured preview

Index entry: `tasks.md` task 5. Design: "Preview". Requirements 6.4–6.6.

## Goal
The viewer shows the embedded textures, base colour where there are none, and
the overlays still work.

## Done when
- [ ] A textured zone renders its textures; a single-mesh GLB without textures
      still renders in base colours.
- [ ] Wireframe works on multi-material meshes; the Trees toggle and terrain
      framing are unaffected.
- [ ] The commit body says what was checked and what wasn't checked live.
- [ ] The frontend builds.
      → verify: `cd web; npx vite build`.

## Pitfalls
- lessons-learned: Z-up camera; movement keys suppressed while typing.
- The commit-message hook blocks two frontend tool words; see lessons-learned.

## Result
