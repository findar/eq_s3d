# Review — traverse adjacency soundness (commit a47385e)

- **Persona lens:** GEOMETRY & NAVIGABILITY REALISM — the "passes tests but
  broken in 3D" lens. The change under review is to the traversability GATE
  itself (`analyzer/traverse.py`), not to generator geometry, so the job is to
  judge whether the gate's new notion of "walkably adjacent" matches what a
  human in the viewer would call walkable, in BOTH directions (no false PASS,
  no false FAIL).
- **Change under review:** `analyzer/traverse.py` only — commit
  `a47385eb944242bafc49d8dfd10822ff3817379d` on branch `agent/m0-hygiene`
  (confirmed `git show --stat` = 1 file, 149 insertions / 10 deletions).
- **Worktree:** `F:\Dev Projects\eq_s3d-worktrees\agent-m0-hygiene`
  (isolated venv `.\.venv\Scripts\python.exe`). MAIN checkout untouched.
- **Reviewer stance:** adversarial; rebuilt the key seed from scratch, traced
  the real BFS path across the real TER mesh, audited every footprint-adjacency
  edge, and ran an old-gate-vs-new-gate regression sweep. Ignored the worker's
  summary and the CI claim and reproduced each.

## What the change does (as read from the diff)

1. Footprint-proximity adjacency now connects two standable faces only when
   their XY footprints genuinely touch — true triangle overlap (vertex-in-tri
   or edge crossing) OR an edge-to-edge gap `<= adjacency_eps`, via the real
   minimum XY distance (`_tri_tri_xy_contact`) after a cheap `_bbox_near`
   pre-reject — instead of a per-axis bbox clip.
2. Floor heights compared at the interpolated **contact point**
   (`_plane_z_at`), not at the two centroids.
3. Shared-vertex pass drops its centroid-Z gate (a shared mesh vertex is one 3D
   point → zero step by construction).

Defaults unchanged (slope 40°, step-up 3.0u, eps 2.0u, player 6.0u).

## Per-acceptance-criterion verdict (geometry-realism lens)

| # | Claim under my lens | Result | Evidence |
|---|---------------------|--------|----------|
| a | corr_26 (room_17↔room_21) is a genuinely walkable, **continuous subdivided ramp** a player could climb — not a gate lie | **MET (analytical); PENDING-HUMAN-3D (render)** | Rebuilt seed 1949459644, prompt "create a dungeon with 30 rooms" → `PASS 30/30`. Reconstructed the actual BFS path from the safe point into room_17 (51 faces). The reach into room_17 is a chain of ~20 consecutive footprint hops whose centroid Z steps down in regular ~2.5u increments (17.0→13.7→11.2→8.7→…→-32.8). Step-at-**contact** on every intermediate hop = `0.000u`; the two landing-transition hops = `2.490u` (< 3.0u cap). corr_26 spec: dz=49.8, run=363, slope **7.8°** (well under the 40° cap). So the ramp is continuous, gentle, flush at both landings — no sub-step the agent admits but a player couldn't. |
| b | The stricter gate does NOT now call a genuinely-walkable continuous floor DISCONNECTED (no false FAIL) — flush coplanar seams, corridor-meets-room joins | **MET** | (i) Old-gate-vs-new-gate room-internal connectivity on seeds 1/7/42 is **identical** (NEW == OLD for every room, e.g. 2/4, 3/6). The change splits nothing the old gate joined. (ii) 20 zone configs (seeds 1,7,42,2,3,100,678358326,55,777,1234 × room_count 6,15) all `PASS` with no room becoming unreachable. (iii) On the 30-room seed, **3127** flush footprint seams (step-at-contact < 0.1u, XY gap ≤ eps) are still welded — the gate keeps genuine same-height corridor↔room joins. |
| c | corr_30 (room_12↔room_17) is a genuine GENERATOR break correctly NOT bridged — a gate success, not a gate bug | **MET** | corr_30 band standable faces span z −32.8 … 123.5 as **multiple flat slabs**, 32 faces below the midline / 31 above, with a 37.8u empty vertical gap between z=26.5 and z=64.2 (and smaller gaps besides). The gate's 3.0u step-up cap correctly refuses to bridge a 37.8u gap. room_17 nonetheless stays reachable via the sound corr_26 ramp — so the broken corr_30 does not disconnect room_17. This matches the "corr_30 is a separate generator follow-up" disposition. The break is in the generated mesh (two/multi-slab floor, no subdivided ramp), not in the gate. |
| d | Full suite green | **MET** | `python -m pytest tests/ -q` in the isolated venv → **240 passed, 2 warnings in 86.30s**, exit 0. The 2 warnings are pre-existing (starlette `BlockingPortal` deprecation + a runpy `server.app` warning), unrelated to this change. |

## Independent adversarial checks (geometry-realism)

- **Whole-mesh footprint-adjacency audit (the key false-PASS test):** on seed
  1949459644 I recomputed step-at-contact for **every** admitted footprint
  (non-vertex) adjacency edge — 3874 edges. **0 edges exceed the 3.0u cap**;
  max admitted = `2.995u` (correctly just under), mean `0.425u`. The gate is not
  teleporting across any real vertical gap. The old gate's failure mode
  (bbox-clip + centroid-Z welding faces tens of units apart) is gone.
- **corr_26 slope/continuity:** the BFS-path trace (above) is the authoritative
  evidence — note that a crude XY-band Z-profile of the corridor region reports
  a misleading ~13u "gap" because the band pulls in room faces and off-centerline
  faces and sorts by projected parameter; the actual walk path shows a clean
  2.5u-per-face descent. This is the exact "wide window gives a misleading gap
  reading" trap the lens warns about — the nearest-contact/per-hop probe (step
  0.0/2.49u) is the honest measure and it reads continuous.
- **Dropping the shared-vertex centroid gate:** `vert_to_faces` is built only
  over standable faces, so only standable↔standable pairs are welded; a shared
  mesh vertex is one 3D point, so the step across that seam is zero by
  construction. This cannot introduce a false PASS across a real step (the step
  is zero at the weld point) and removes a spurious false-FAIL proxy.

## Findings

### NIT-1 — corridor-band Z-profile is a misleading measurement (reviewer-side only; NOT a code issue)
- **Severity:** NIT (no action on the worker).
- **Note:** a naive "faces near the corridor XY segment within a Z band, sorted
  by run parameter" probe reports a spurious large consecutive-Z jump on corr_26
  because it mixes in room/off-axis faces. Anyone re-verifying should trace the
  actual BFS path / step-at-contact rather than a wide spatial window — the gate
  logic itself is correct; this is purely a verification-method caveat so the
  next reviewer doesn't misread corr_26 as broken.

### NIT-2 — single-shared-vertex welds are now ungated (same as correctness persona's NIT-2)
- **Severity:** NIT.
- **Problem:** two standable triangles meeting at exactly ONE vertex (a corner,
  not a shared edge) are welded with no step check. For the box dungeon backend
  this is harmless (floor tiles meet edge-to-edge at the same height), and it is
  strictly a loosening of a gate that was already permissive. If a future
  non-box backend produces standable faces sharing a single corner across a real
  step, reconsider gating the shared-vertex pass on edge-shared (2 common verts)
  vs. corner-shared (1 vert). Not needed for the box backend this change targets.
- **What would clear it (optional):** nothing for this task.

No BLOCKERs found under the geometry-realism lens.

## What I could NOT independently verify (stated plainly)

- **The actual 3D render.** I cannot see the viewer. I verified the gate's
  adjacency logic and the reachability walk on the REAL generated TER mesh, and
  the ramp's per-hop geometry analytically. Because the change is
  adjacency-logic-only (no geometry/generator change — confirmed 1-file diff),
  it cannot alter rendered geometry; the gate is now a STRICTER reporter of the
  same mesh. But the standing repo lesson is "structural tests pass ≠ looks
  right in 3D." A human must still walk `docs/ACCEPTANCE.md` **section B**
  (Navigability) on **seed 1949459644**, prompt "create a dungeon with 30
  rooms", and confirm by eye:
    - **[MUST] Rooms are reachable / Corridors connect cleanly / Stairs are
      continuous** — walk the corr_26 ramp (room_21 → room_17); confirm it is a
      single continuous slope flush at both landings, not a visible step or gap.
    - Confirm the corr_30 (room_12↔room_17) slab break looks broken in the
      viewer (it should — it is handed off as a generator follow-up, NOT fixed
      here), and that room_17 is still walkable via corr_26.
  Recommend also eyeballing clean seeds 1 / 7 / 42 (room_count 6) and the
  repo's standing corridor seeds 1955208177 / 1516796975 / 481893615 per
  section B, since the gate that polices those is what changed.
- **No dedicated `tasks/<id>.md`** exists for this specific traverse-soundness
  change in the worktree; I reviewed against the spawning directive's criteria
  a/b/c plus `docs/ACCEPTANCE.md` section B. (The change is not a numbered item
  in `.kiro/specs/zone-generator-m0-hygiene/tasks.md`.)

## Housekeeping note

My throwaway verification scripts and rebuilt zone artifacts live under the
gitignored, per-worktree `output/` directory (confirmed `git check-ignore`
matches them), so they do not appear in `git status` and cannot pollute any
commit. The sandbox denied `Remove-Item`, so they remain on disk in `output/`
only; they are inert. The sole untracked repo file is the other persona's
review, which I did not touch.

## Conclusion

Under the geometry-realism lens the change is sound in both directions I own:
it removes false-PASS bridges (whole-mesh audit: 0 footprint edges over the
3.0u cap; the two named false bridges gone) WITHOUT introducing any false FAIL
(old-vs-new room-internal connectivity identical; 20/20 zone configs PASS;
3127 flush seams still welded). The reach into room_17 is a genuine continuous
2.5u-step ramp (corr_26, 7.8° slope), and corr_30's multi-slab 37.8u gap is a
real generator break the gate correctly refuses to bridge — a gate success and
a separate follow-up, not a gate bug.

The ONLY thing left is the one thing I structurally cannot do: confirm the
render by eye. Per the repo's standing rule that a green suite is necessary but
not sufficient for a visual-adjacency change, the corr_26 ramp and the corr_30
break must be walked in the live viewer on seed 1949459644 (section B). I found
no BLOCKER and nothing I could analytically verify is wrong; the remaining gate
is a human-3D eyeball.

VERDICT: PENDING-HUMAN-3D
