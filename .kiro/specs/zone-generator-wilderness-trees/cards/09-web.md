# 9 — Web: Trees selector and vegetation toggle

Index entry: `tasks.md` task 9. Requirements 3.4, 9.2.

## Goal
The Controls panel offers a Trees selector beside the Edges selectors
(wilderness only), and the viewer has a keyboard-reachable toggle that hides and
shows the `vegetation` node.

## Done when
- [x] The selector sends `controls.trees`; it's hidden for other zone types.
- [x] The toggle flips the `vegetation` node's visibility; with no such node it
      is disabled.
- [x] Camera framing and walking still work now that the GLB can hold two nodes
      (design "Risks"); say what you checked.
- [x] The frontend builds.
      → verify: `cd web; npx vite build`.

## Pitfalls
- lessons-learned: "Movement keys must be suppressed while typing".
- App worktrees have no `web/node_modules`; install your own copy
  (`npm install --no-package-lock`), never a junction.
- The commit-message hook blocks two frontend tool words; see lessons-learned.

## Result
✔ 7f01374 · 654 passed
