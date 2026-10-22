# Review — traverse adjacency soundness fix (commit a47385e)

- **Persona lens:** ARCHITECTURE & CONVENTIONS
- **Branch / worktree:** `agent/m0-hygiene` @ `F:\Dev Projects\eq_s3d-worktrees\agent-m0-hygiene`
- **Commit under review:** `a47385e` — "analyzer/traverse: make walk adjacency sound (true XY contact + Z-at-contact)"
- **Reviewer constraints:** read-only; did not touch MAIN checkout, did not edit code/tests/task files, did not alter git state.
- **Date:** 2026-10-21 22:35

## What I did to reproduce (don't-trust log)

- `git show --stat a47385e` + `git show --name-only` — diff is **only** `analyzer/traverse.py` (+149/-10).
- `git show --stat a47385e -- ROADMAP.md README.md tasks/README.md` — **empty**; no tracker files in the commit.
- Read the full diff and the surrounding `build_walk_surface` body (traverse.py ~309–470).
- `.\.venv\Scripts\python.exe -m pytest tests/ -q` → **240 passed, 2 warnings** (84s). Matches the commit's claim.
- Generated `--rooms 30 --seed 1949459644` (dungeon) and `python -m analyzer.traverse` → all 30 rooms OK (no false FAIL under the stricter gate).
- Clean seeds 1/7/42 (rooms=6) → all `Traversability: validated`.
- Seed sweep 2,3,4,5,100,999,12345 @ rooms=30 → all `[PASS]`.
- `git branch -vv` / `git branch -r` → branch is **local-only**, no upstream, not pushed.
- Grepped `tests\*.py` for `_tri_tri_xy_contact|_plane_z_at|_point_in_tri|_seg_seg|_bbox_near` → **no test references** the new helpers.
- Read `tests/test_traversability.py` and `tests/test_properties_build.py` to see what the suite actually asserts.
- Read `tasks/traversability-validator.md` (the related task file) and scanned `.kiro/specs/zone-generator-m0-hygiene/tasks.md`.

## Per-architectural-point assessment

| # | Architectural point | Verdict | Evidence |
|---|---------------------|---------|----------|
| 1 | Root-cause vs seed-overfit patch | **Met** | Fix replaces a per-axis bbox clip + centroid-Z proxy with a true min XY triangle-distance test (`_tri_tri_xy_contact`) and interpolated floor height at the contact point (`_plane_z_at`). This is a general geometric soundness fix, not a seed-specific special-case. No seed literals, thresholds, or face indices appear in the code path. Defaults unchanged. |
| 2 | Scope / module seams (gate only; no generator geometry) | **Met** | Commit touches only `analyzer/traverse.py`. No `generators/*`, no sidecar, no `*.zone.json`. `analyzer/` owns the gate; the seam is respected. |
| 3 | Didn't cripple the gate to force criterion A (room_17 UNREACHABLE) | **Met** | Worker determined the premise was false (room_17 reachable via sound corr_26), kept the gate SOUND, flagged corr_30 as a separate generator bug, and got explicit user approval to land as-is. Correct call: forcing a FAIL on a broken-but-non-disconnecting corridor would make the gate *unsound* (report a reachable room as unreachable). Not lowering/rewriting the bar — raising a real premise error. |
| 4 | Single-writer tracker ownership | **Met** | `git show --stat` confirms ROADMAP.md / README.md / tasks/README.md not in the commit. `tasks/traversability-validator.md` is the already-landed *build* task (Status: done, commit 48b08c8) — correctly left untouched; editing a landed done-file would rewrite integration state. No dedicated task file exists for this hygiene fix. |
| 5 | Commit hygiene | **Met** | One logical change (adjacency soundness). Message avoids the blocked frontend-build-tool words (grep for `Vite`/`dev server` → empty). Working tree clean except the two untracked peer-review files. Branch local-only, not pushed. Hash recorded here: `a47385e`. |
| 6 | North-star: sound navigability gate, pacing/gating stays advisory | **Met** | Strengthening the gate directly serves "navigable floors verified by a sound walkability gate." No geometry/collision/sidecar touched, so pacing/gating stay advisory. Z-up unaffected. |

## Findings

### NIT-1 — No regression test for the exact false-PASS this commit fixes
- **Severity:** NIT (does not gate the pass, but strongly recommended per steering "add regressions for bug fixes").
- **Problem:** The bug fixed is a **false-PASS / soundness** defect: two *individually standable* (near-flat) faces that are offset in XY or stacked in Z were wired together, letting the flood fill teleport across a real gap. The suite guards only (a) the no-false-FAIL direction (`TestKnownGoodDungeons`, `test_properties_build` asserting `report.passed` on good zones) and (b) one soundness case that is **slope-based** (`TestValidatorFlagsBreakage` uses a 56° cliff ramp, rejected by the standable-normal / `classify_corridor` path — not by `_tri_tri_xy_contact`/`_plane_z_at`). The new contact logic has no test that would go red if it were reverted.
- **Evidence:** grep of `tests\*.py` for the new helper names → no matches. Read of `test_traversability.py`: the only soundness assertion is the cliff-ramp spec, whose failure mode is slope, not XY non-contact. `test_properties_build.py` only asserts `report.passed` (good-zone direction). I generated seeds 2–12345 @ rooms=30 and all PASS, so the live `--rooms` generator path does not currently produce a flat-but-non-touching false bridge to catch this by accident either.
- **What would clear it:** Add a deterministic regression — a hand-built `ZoneSpec` (like the existing `_cliff_spec`) with two **flat, standable** floor slabs that (i) overlap in one XY axis but are offset >`adjacency_eps` on the other, or (ii) sit at the same XY but differ in Z by >`max_step_up`, joined so the OLD code would bridge them and the far room would read reachable. Assert the far room is now `not reachable`. Alternatively a unit test on `_tri_tri_xy_contact` asserting bbox-clipping-but-geometrically-distant triangles return `dist > eps`. This is the guard that makes the fix stick; without it a future refactor can silently reintroduce the false PASS.

### NIT-2 — Stale docstring on `build_walk_surface`
- **Severity:** NIT.
- **Problem:** The `build_walk_surface` docstring still says adjacency means "their XY bounding boxes overlap within `adjacency_eps` and their XY regions actually intersect" — the bbox-overlap framing is exactly the old (now-superseded) behaviour. The inline block comment below was updated; this top docstring was not.
- **Evidence:** traverse.py, `build_walk_surface` docstring (~line 318), vs the updated pass-2 comment (~line 372).
- **What would clear it:** reword the docstring to describe true XY footprint contact + floor-height-at-contact, matching the implemented logic.

## Things I could NOT independently verify (stated plainly)

- **The exact named false bridges (faces 2642↔132, 3146↔132) on prompt "create a dungeon with 30 rooms" seed 1949459644.** That scenario comes from the **prompt/planner** path; the CLI only exposes `--rooms`/`--seed`, which routes through `LayoutGenerator` and produced a *clean* PASSing zone for that seed. I therefore could not reproduce the specific broken corr_30 geometry or the two face-pairs byte-for-byte. I verified the fix's *soundness properties* instead (240-test suite green, no false FAIL on clean/elevated seeds, scope confined to the gate), which is the architecture-lens bar; the per-face claim I take as unverified.
- **Whether the gate now correctly REJECTS a flat-but-non-touching pair in a live generated zone.** No `--rooms` seed in my sweep realised that geometry, and there is no regression test (NIT-1), so this direction is covered only by the code reading, not an executed red/green.
- **Visual 3D correctness** is out of my lens (geometry persona + the corr_30 follow-up own that); I make no claim on it.

## Verdict rationale

Architecturally this is a clean, principled, correctly-scoped fix: gate-only, no tracker writes, root-cause (true geometric contact) rather than a patch, branch local-only, one logical commit, and a sound refusal to cripple the gate for a false premise. The only findings are NITs — a missing regression test for the fixed false-PASS and one stale docstring — neither of which gates a PASS. I recommend the worker add the regression (NIT-1) before this is leaned on, but it is not a blocker.

VERDICT: PASS
