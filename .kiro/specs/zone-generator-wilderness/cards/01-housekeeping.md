# 1 — Housekeeping: land waves 1–4 on the trackers

Index entry: `tasks.md` task 1. Runs in the **MAIN checkout**, not a worktree:
it is the single-writer integration step, and it is the only task allowed to
edit `ROADMAP.md`, `README.md` and `tasks/README.md`.

## Goal
Waves 1–4 of the wilderness generator are merged into `master`, but the project
trackers still describe the world before them. Their integration notes were
never applied, four merged worktrees are still on disk, and `master` is about
40 commits ahead of `origin`. Bring the trackers and the disk back in line with
the code, so the next agent starts from an accurate picture.

## Done when
- [ ] `ROADMAP.md` "Pick up here" names wilderness task 2. The Done table gains
      one row for "wilderness waves 1–4" (merged at `917bae3`). Take the facts from
      `archive.md`, not from memory.
      → verify: read the diff.
- [ ] The four worktrees are removed with the helper, never with a bare
      `git worktree remove` (see lessons-learned, junction trap):
      `./scripts/remove-worktree.ps1 -Branch agent/wild-matrix -DeleteBranch`, and
      the same for `agent/wild-rewrite`, `agent/wild-synth`, `agent/wild-bowl`.
      → verify: `git worktree list` shows only the main checkout; `cd web; npx vite build` still succeeds (the node_modules junction is intact).
- [ ] `.kiro/specs/zone-generator-followup/` and the M0–M6 "Delivery plan" in
      `.kiro/specs/zone-generator/design.md` each carry a one-line banner at the
      top: `STATUS: superseded by the 11-step content roadmap in ROADMAP.md`.
      → verify: read the diff.
- [ ] `.kiro/specs/zone-generator-m2-true-layout-artifacts/` has a decision
      recorded in its `requirements.md` header: either it maps to a roadmap
      step, or it is parked. **This is the user's decision. Ask; don't pick.**
- [ ] `git push origin master` (the backup remote; project rule).

## Pitfalls
- `-DeleteBranch` uses `git branch -d`, which refuses an unmerged branch. All
  four are merged into `master`, so a refusal means something is wrong. Stop
  and report it; don't reach for `-Force`.
- Don't touch any code. No tests are needed; this task changes docs only.

## Result
<!-- worker: one line, e.g. "✔ abc1234 · pushed · 4 worktrees removed" -->
