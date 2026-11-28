# P-9 Engineering — design (living)

Checked against the code at master `c3d9b99` (2026-11-27, the commit that opened the project-docs spec). Shell and Windows gotchas are in
[lessons-learned "Environment / tooling"](../../../.kiro/steering/lessons-learned.md#environment--tooling-windows--powershell).

## Tests

[`pytest.ini`](../../../pytest.ini) runs `-n auto --dist worksteal`. Markers: `slow` (a build-level property, a
pipeline run, or anything 10 s or more at the timed worker count) and `gate` (a sweep of many
builds through the gate). Hypothesis profiles in [`tests/conftest.py`](../../../tests/conftest.py): default (derandomised),
`quick` (25 examples), `thorough` (5 times the default).

| Tier | Command | When | Size (measured in [step 28](../../../.kiro/specs/test-speed/tasks.md)) |
|---|---|---|---|
| Quick | `python -m pytest tests/ -q -m "not slow and not gate" --hypothesis-profile quick` | every edit | ~210 s, ~3030 tests |
| Full | `python -m pytest tests/ -q` | once, alone, at a task's close | ~1320 s, ~13 GB |
| Gate | `python -m pytest tests/ -q -m gate` | after geometry, layout or gate changes | ~770 s, 702 tests |

`EQ_PATH` must point at the RoF2 install for decor and stock-survey tests. One heavy suite at a
time per machine. Byte checks compare `.eqg` bytes without the 4-byte footer.

## Reproducibility

Seeds are 31-bit; stable sub-seeds use `zlib.crc32` of their parts, never Python's salted
`hash()`, which changes from run to run. A build records the seeds it used in the sidecar and `<name>.request.json`. Pinned
seeds are never swapped. A test ([`tests/test_build_order.py`](../../../tests/test_build_order.py)) checks a zone builds the same alone
or after others in one process.

## Safety

- The server binds `127.0.0.1:8000` with an explicit CORS list (the page's two origins) and
  `reload=False`.
- Every write goes through `core/paths.OutputRoot`, which resolves and confines paths to the
  output root (stripping a `\\?\` long-path prefix that Windows can leave under a race) and removes trees without following
  junctions. The EQ install is refused as an output.
- File routes validate each path segment with `fullmatch`.

## Agents and trackers

- One worktree per agent (`scripts/new-worktree.ps1 -Branch agent/<scope>`), torn down from the
  main checkout with [`scripts/remove-worktree.ps1`](../../../scripts/remove-worktree.ps1) (a bare `git worktree remove` follows the
  `node_modules` junction into the main repo).
- Card-format specs: `tasks.md` is an index (checkbox, Card, Type, Size, Depends, Owns); the card
  says what to do and holds a one-line Result. Evidence goes in commits with a
  `Task: <spec>/<n>` trailer; `python scripts/task_status.py` lists ready tasks and which can run
  side by side.
- [`ROADMAP.md`](../../../ROADMAP.md), [`README.md`](../../../README.md) and [`tasks/README.md`](../../../tasks/README.md) are written only in the integration step from
  the main checkout (single-writer, unconditional).

## Performance (what costs what)

- A 30-room cave Graph Draw takes about 3.2 s ([step 29](../../../.kiro/specs/zone-generator-cave-clumps/tasks.md)). A rough 30-room build took about 32 s
  ([step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md)), before `6e10e38` ([step 28](../../../.kiro/specs/test-speed/tasks.md)) moved the gate's hot loops onto arrays.
- Outside the gate a sweep build is dominated by decor placement, map outline and outline
  containment ([step 28](../../../.kiro/specs/test-speed/tasks.md)).
- The slowest generates are outdoor-dungeon Draws (a 30-room `ice_keep` took 223 s, [step 19](../../../.kiro/specs/zone-generator-quality/tasks.md));
  [step 33](../../../.kiro/specs/zone-generator-layout-repair/tasks.md) is measuring where generate time goes.

## Docs

| Doc | Holds |
|---|---|
| [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) | the pipeline, the IR, the module map, the north-star rules, the glossary |
| [`docs/STYLE.md`](../../STYLE.md) | house rules for docs: IDs, references and links, plain language |
| `docs/pillars/<pillar>/` | `PLAN.md`, `DESIGN.md` (living), `DECISIONS.md`, `OPEN.md` |
| [`OPEN.md`](../../../OPEN.md) | every open item, one roll-up |
| [`ROADMAP.md`](../../../ROADMAP.md) | in flight, next, the Done table (one page after [project-docs task 4](../../../.kiro/specs/project-docs/cards/04-roadmap.md)) |
| [`docs/ACCEPTANCE.md`](../../ACCEPTANCE.md) | the manual 3D checklist per slice (split per slice in task 4) |
| [`.kiro/steering/`](../../../.kiro/steering) | always-on rules and lessons for agents |
| [`.kiro/specs/`](../../../.kiro/specs) | one spec per slice; closed ones move under their pillar in task 3 |
