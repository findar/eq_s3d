# P-9 Engineering — open items

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

IDs are `P-9-<k>`. The columns are explained in [P-1's `OPEN.md`](../P-1-web-app/OPEN.md). Roll-up: [`OPEN.md`](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| <a id="p-9-1"></a>P-9-1 | No CI, releases, migrations of saved builds and specs across format changes, or user docs beyond the README | gap 2026-11-27 | open | code: no `.github/` |
| <a id="p-9-2"></a>P-9-2 | No failure dashboard: `output/validation_failures.jsonl` and sweep results have no viewer or summary | gap 2026-11-27 | open | code |
| <a id="p-9-3"></a>P-9-3 | A heavy-run lock so agents don't run full, gate or sweep runs at once | [project-docs requirement 6](../../../.kiro/specs/project-docs/requirements.md#requirements) | in flight ([project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md)) | — |
| <a id="p-9-4"></a>P-9-4 | Build time outside the gate: decor placement, map outline, [`generators/outline.py`](../../../generators/outline.py) containment | [step 28 archive](../../../.kiro/specs/test-speed/archive.md) | in flight ([step 33](../../../.kiro/specs/zone-generator-layout-repair/tasks.md) task 1 measures) | — |
| <a id="p-9-5"></a>P-9-5 | `test_corridor_clearance::test_no_corridor_clips_a_room_over_the_sweep` is one ~271 s call; split it per case (`test_bridges` similar) | steps [12](../../../.kiro/specs/zone-generator-world-sockets/archive.md) and [28](../../../.kiro/specs/test-speed/archive.md) archives | open | code: one `@pytest.mark.slow` test |
| <a id="p-9-6"></a>P-9-6 | Stale "no `slow` marker" comments in [`tests/test_properties_layout.py`](../../../tests/test_properties_layout.py) | [step 28 archive](../../../.kiro/specs/test-speed/archive.md) | open | code: lines 57, 123, 181 |
| <a id="p-9-7"></a>P-9-7 | Cave draw time outside [`embed.py`](../../../generators/topology/embed.py) (~1.7–2.1 s of a 30-room cave); `start_positions` and `_untangle` (partly done by `e9cfd89`, faster cave bearing draws) | steps [27](../../../.kiro/specs/zone-generator-random-placement/archive.md) and [29](../../../.kiro/specs/zone-generator-cave-clumps/archive.md) archives | open | record |
| <a id="p-9-8"></a>P-9-8 | Slow outdoor-dungeon Draws: 67 of 405 over 30 s; a 30-room `ice_keep` (seed 1100087430) 223 s | [step 19 archive](../../../.kiro/specs/zone-generator-quality/archive.md) | in flight ([step 33](../../../.kiro/specs/zone-generator-layout-repair/tasks.md)) | record |
| <a id="p-9-9"></a>P-9-9 | Rough 30-room builds about 32 s, the gate's seam test the slowest step: re-measure after `6e10e38` ([step 28](../../../.kiro/specs/test-speed/tasks.md): the gate's hot loops on arrays) | [step 8 archive](../../../.kiro/specs/zone-generator-room-walls/archive.md) | open (re-measure) | record |
| <a id="p-9-10"></a>P-9-10 | A parallel test run once hung with its workers gone; unexplained | [ROADMAP](../../../ROADMAP.md); [lessons-learned](../../../.kiro/steering/lessons-learned.md) | parked | — |
| <a id="p-9-11"></a>P-9-11 | The shared Python env drifts from the pins (fastapi, starlette, hypothesis, httpx) | [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) | open (environment) | code: [`requirements.txt`](../../../requirements.txt) pins `fastapi==0.115.6` |
| <a id="p-9-12"></a>P-9-12 | The PFS footer timestamp keeps two `.eqg` writes from being byte-identical | [ROADMAP](../../../ROADMAP.md); [lessons-learned](../../../.kiro/steering/lessons-learned.md) | parked (tests compare `bytes[:-4]`) | code |
| <a id="p-9-13"></a>P-9-13 | The inspector's ASCII bounding-box diagram has no Z (side-elevation) view | [ROADMAP "Known issues"](../../../ROADMAP.md#known-issues--smaller-fixes) | open | record |
| <a id="p-9-14"></a>P-9-14 | **[ZG-Req-33](../../../.kiro/specs/zone-generator/requirements.md#introduction) (the `cave` Purpose) is cited but never written** in [`.kiro/specs/zone-generator/requirements.md`](../../../.kiro/specs/zone-generator/requirements.md), and is missing from its traceability table | found by [project-docs task 1](../../../.kiro/specs/project-docs/cards/01-proposal.md) | open | code |
| <a id="p-9-15"></a>P-9-15 | **The umbrella design describes modules that don't exist and won't**: `server/sessions.py`, `ai/edit_interpreter.py`, `generators/meshcache.py`, `generators/natural.py`, `analyzer/conformance.py`, `textures/normals.py`; its backend table still says wilderness is disabled and on room pads; steering's "GLB preview uses base colours, not textures" has been wrong since [step 3](../../../.kiro/specs/zone-generator-placeholder-textures/tasks.md) | found by [project-docs task 1](../../../.kiro/specs/project-docs/cards/01-proposal.md) | in flight ([project-docs tasks 3](../../../.kiro/specs/project-docs/cards/03-move.md) and 4) | code |
| <a id="p-9-16"></a>P-9-16 | Docs organised by history: [ROADMAP](../../../ROADMAP.md)'s 13,000-character "Pick up here", 25 "Carried from" chains, a 4,593-line ACCEPTANCE | [project-docs requirements](../../../.kiro/specs/project-docs/requirements.md#introduction) | in flight ([project-docs tasks 3](../../../.kiro/specs/project-docs/cards/03-move.md) to 6) | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| Same seed, different build when another zone was built first in one process | `6781622` ([step 32](../../../.kiro/specs/zone-generator-races-followups/tasks.md) task 2: the stock model cache is keyed by actor, not mesh) |
| Dependency residue (`scikit-image`, `fast-simplification`, `flask`) | merge `b0d412f` ([M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md): hygiene and the property test harness) |
| The parallel runner's first-run collection mismatch (`\\?\` prefix race) | `core/paths._resolve` ([lessons-learned](../../../.kiro/steering/lessons-learned.md#environment--tooling-windows--powershell)) |
