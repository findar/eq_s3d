# Engineering — open items

Status and Checked as in [P-A's OPEN](../P-A-web-app/OPEN.md). Roll-up: [OPEN.md](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| X-1 | No CI, releases, migrations of saved builds and specs across format changes, or user docs beyond the README | gap 2026-11-27 | open | code: no `.github/` |
| X-2 | No failure dashboard: `output/validation_failures.jsonl` and sweep results have no viewer or summary | gap 2026-11-27 | open | code |
| X-3 | A heavy-run lock so agents don't run full, gate or sweep runs at once | project-docs requirement 6 | in flight (project-docs task 5) | — |
| X-4 | Build time outside the gate: decor placement, map outline, `generators/outline.py` containment | step 28 archive | in flight (step 33 task 1 measures) | — |
| X-5 | `test_corridor_clearance::test_no_corridor_clips_a_room_over_the_sweep` is one ~271 s call; split it per case (`test_bridges` similar) | steps 12, 28 archives | open | code: one `@pytest.mark.slow` test |
| X-6 | Stale "no `slow` marker" comments in `tests/test_properties_layout.py` | step 28 archive | open | code: lines 57, 123, 181 |
| X-7 | Cave draw time outside `embed.py` (~1.7–2.1 s of a 30-room cave); `start_positions` and `_untangle` (partly done by `e9cfd89`) | steps 27, 29 archives | open | record |
| X-8 | Slow outdoor-dungeon Draws: 67 of 405 over 30 s; a 30-room `ice_keep` (seed 1100087430) 223 s | step 19 archive | in flight (step 33) | record |
| X-9 | Rough 30-room builds about 32 s, the gate's seam test the slowest step: re-measure after `6e10e38` | step 8 archive | open (re-measure) | record |
| X-10 | A parallel test run once hung with its workers gone; unexplained | ROADMAP; lessons-learned | parked | — |
| X-11 | The shared Python env drifts from the pins (fastapi, starlette, hypothesis, httpx) | ROADMAP Known issues | open (environment) | code: `requirements.txt` pins `fastapi==0.115.6` |
| X-12 | The PFS footer timestamp keeps two `.eqg` writes from being byte-identical | ROADMAP; lessons-learned | parked (tests compare `bytes[:-4]`) | code |
| X-13 | The inspector's ASCII bounding-box diagram has no Z (side-elevation) view | ROADMAP Known issues | open | record |
| X-14 | **Umbrella Requirement 33 (the `cave` Purpose) is cited but never written** in `.kiro/specs/zone-generator/requirements.md`, and is missing from its traceability table | found by this proposal | open | code |
| X-15 | **The umbrella design describes modules that don't exist and won't**: `server/sessions.py`, `ai/edit_interpreter.py`, `generators/meshcache.py`, `generators/natural.py`, `analyzer/conformance.py`, `textures/normals.py`; its backend table still says wilderness is disabled and on room pads; steering's "GLB preview uses base colours, not textures" is wrong since step 3 | found by this proposal | in flight (project-docs tasks 3–4) | code |
| X-16 | Docs organised by history: ROADMAP's 13,000-character "Pick up here", 25 "Carried from" chains, a 4,593-line ACCEPTANCE | project-docs requirements | in flight (project-docs tasks 3–6) | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| Same seed, different build when another zone was built first in one process | `6781622` (step 32 task 2) |
| Dependency residue (`scikit-image`, `fast-simplification`, `flask`) | M0, merge `b0d412f` |
| The parallel runner's first-run collection mismatch (`\\?\` prefix race) | `core/paths._resolve` (lessons-learned) |
