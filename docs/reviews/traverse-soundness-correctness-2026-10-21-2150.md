# Review — traverse adjacency soundness (commit a47385e)

- **Persona lens:** CORRECTNESS & VERIFICATION
- **Change under review:** `analyzer/traverse.py` only — commit
  `a47385eb944242bafc49d8dfd10822ff3817379d` on branch `agent/m0-hygiene`.
- **Worktree:** `F:\Dev Projects\eq_s3d-worktrees\agent-m0-hygiene`
  (isolated venv `.\.venv\Scripts\python.exe`). MAIN checkout untouched.
- **Reviewer stance:** adversarial; reproduced every claim from scratch, ignored
  the worker's summary and CI claim.

## What the change does (as read from the diff)

1. Footprint-proximity adjacency pass now connects two standable faces only when
   their XY footprints genuinely touch — true triangle overlap (vertex-in-tri or
   edge crossing) OR an edge-to-edge gap `<= adjacency_eps`, via the real minimum
   XY distance (`_tri_tri_xy_contact`) — after a cheap `_bbox_near` pre-reject.
2. Floor heights compared at the interpolated contact point (`_plane_z_at`), not
   at the two centroids.
3. Shared-vertex pass drops its centroid-Z gate (a shared mesh vertex is one 3D
   point, zero step by construction).

Defaults unchanged (slope 40°, step-up 3.0u, eps 2.0u, player 6.0u).

## Per-acceptance-criterion verdict

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| A | Seed 1949459644, "dungeon 30 rooms": named false bridges 2642↔132 and 3146↔132 rejected; room_17 reachable via the SOUND corr_26 ramp, not a surviving false bridge | **MET** | Rebuilt the zone. `traverse: PASS 30/30`. Both named pairs: `in_mesh=True both_standable=True connected=False` — correctly rejected. Reconstructed the BFS path from the safe point into room_17 (51 faces): every footprint hop's step-at-contact is `0.00u` except two `2.49u` hops (the subdivided corr_26 ramp) — worst footprint hop = **2.49u < 3.0u cap**. corr_30 (room_12↔room_17) slab z-range sampled `[-32.8 … 123.5]` with a clear mid gap — the gate refuses to bridge it, matching the "corr_30 is a separate generator follow-up" disposition the user approved. |
| A′ | No OTHER false bridge keeps room_17 reachable | **MET** | Full-mesh audit of every footprint adjacency edge on this seed: **0 edges** exceed the 3.0u step-at-contact cap; max admitted = `2.995u` (correctly just under). room_17's reached faces join the graph only via shared-vertex seams (step 0) and the 2.49u ramp hops. |
| B | Clean dungeons `theme='dungeon', room_count=6, elevation=True`, seeds 1/7/42 stay PASS | **MET** | Rebuilt all three: `seed 1: PASS 6/6`, `seed 7: PASS 6/6`, `seed 42: PASS 6/6`. |
| C | Full suite `pytest tests/ -q` reports 240 passed, 0 failed | **MET** | Re-ran in the isolated venv: `240 passed, 2 warnings in 84.55s`, exit 0. The 2 warnings are pre-existing (starlette `BlockingPortal` deprecation + a runpy `server.app` warning), unrelated to this change. |

## Independent adversarial checks (beyond the stated criteria)

All passed — none surfaced a BLOCKER.

- **Geometry-helper edge cases** (`_point_in_tri_xy`, `_seg_seg_closest_xy`,
  `_tri_tri_xy_contact`, `_plane_z_at`): inside/edge/vertex/outside point tests,
  crossing / parallel-gap / collinear-overlap / shared-endpoint / degenerate
  segment cases, tri overlap / fully-contained / fixed-gap cases, planar Z
  interpolation + degenerate-triangle mean-Z fallback — all returned the
  expected values. The collinear-overlap segment case (which the strict-CCW
  proper-intersection branch deliberately does NOT fire on) is correctly caught
  as distance 0 by the point-segment fallback.
- **bbox pre-reject soundness:** 200k random triangle pairs; of the 144,437 with
  true XY distance `<= eps`, `_bbox_near` returned False **0** times. The cheap
  pre-reject never discards a genuine contact (it is conservative by
  construction — a `<=eps` gap forces the eps-expanded boxes to overlap).
- **Dropping the shared-vertex centroid gate — could it weld a standable face to
  a near-vertical sliver or across a large step away from the shared vertex?**
  No. `vert_to_faces` is built only over `std_idx`, so only standable↔standable
  pairs are welded; a near-vertical face is never standable and never enters the
  pass. Empirically, across a 30-zone sweep the worst shared-vertex *centroid*
  Z-span was **0.8u** — the box backend never produces standable faces sharing a
  vertex with a meaningful Z span, so the loosening has no practical effect.
- **No-false-FAIL regression sweep (the key correctness test):** ran the OLD
  (parent `ddab54a`) gate and the NEW gate side by side over 20 seeds × room
  counts {6,15,30} = 60 zones. **OLD-pass / NEW-fail count = 0.** The stricter
  footprint test never flips a previously-accepted zone to FAIL. The change is a
  pure removal of false PASSes with no new false FAILs.

## Findings

### NIT-1 — seed 99, room_count=15 fails under BOTH old and new gates (pre-existing, not this change)
- **Severity:** NIT (does not gate this change).
- **Problem:** `LayoutGenerator('dungeon', seed=99).generate(room_count=15)`
  validates `FAIL 0/15`. The safe point `(1145, -56, 5.0)` lands on a geometry
  fragment whose flood reaches only 26 of 1284 standable faces, and the seed
  face is in no room.
- **Evidence:** old-vs-new sweep — `Both FAIL: seed 99 rc 15`. So this is a
  pre-existing broken-zone / safe-point-placement issue, NOT introduced by
  a47385e. The pipeline gates on `traverse` with fresh-seed retries, so such a
  zone is regenerated, never shipped.
- **What would clear it:** nothing required for THIS task. Worth a separate
  generator/safe-point follow-up ticket (entrance safe point not landing on the
  entrance room floor on some seeds).

### NIT-2 — single-shared-vertex welds are now ungated
- **Severity:** NIT.
- **Problem:** two standable triangles touching at exactly ONE vertex (a corner,
  not a shared edge) are now welded with no step check at all. In principle an
  agent can't always walk across a single corner point, and two standable ramps
  meeting only at an apex could differ in height away from that vertex.
- **Evidence/why it's only a NIT:** the behaviour is strictly a loosening of a
  gate that was already permissive (the old code also connected single-vertex
  pairs, just with a centroid proxy); and the empirical sweep shows the box
  backend never produces such a pair with a span worth gating (max 0.8u). No
  observed false connect.
- **What would clear it (optional):** if a future non-box backend produces
  standable faces sharing a single vertex across a real step, reconsider gating
  the shared-vertex pass on an edge-shared (2 common vertices) vs. corner-shared
  (1 vertex) distinction. Not needed for the box backend this task targets.

## What I could NOT independently verify

- **3D-viewer appearance.** This is the correctness lens; I verified the gate's
  *logic* and *reachability math* on the real generated mesh, not how the zone
  looks in the viewer. The change is adjacency-logic-only (no geometry/generator
  change, confirmed: `git show --stat` = 1 file, `analyzer/traverse.py`), so it
  cannot alter rendered geometry — but the GEOMETRY & NAVIGABILITY persona should
  still confirm the corr_26 ramp and the room_17 join per `docs/ACCEPTANCE.md`
  section B on seed 1949459644, and the corr_30 break is handed off as a
  generator follow-up (not fixed here, per the user's approval).
- **The `corridor-connection` task file** (`tasks/corridor-connection.md`) is the
  nearest existing tracker entry but predates this soundness fix; the acceptance
  criteria I reviewed against came from the spawning directive. No dedicated
  `tasks/<id>.md` for this specific traverse-soundness change exists in the
  worktree, so I treated the directive's A/B/C as the bar.

## Conclusion

I tried hard to break it: edge-case probes of all four new helpers, a bbox
pre-reject soundness proof (144k contacts), a shared-vertex span audit, a full
BFS-path step audit on the flagged seed, a whole-mesh footprint-edge scan, and a
60-zone OLD-vs-NEW regression sweep. The change does exactly what it claims —
removes the false bridges (2642↔132, 3146↔132 now rejected; room_17 reachable
only via the sound 2.49u corr_26 ramp) — and adds **no** false FAILs on any
zone the old gate accepted. Suite is 240/240. The two NITs are a pre-existing
unrelated seed-99 break and a theoretical single-vertex-weld loosening with no
observed impact on the box backend; neither gates the pass.

VERDICT: PASS
