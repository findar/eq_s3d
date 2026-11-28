# P-6 Iterative feedback — design (living)

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Checked against the code at master `c3d9b99` (2026-11-27, the commit that opened the project-docs spec).

## Versions are the history

- Generate makes `v1` of a zone in `output/web/<zone>/v1/`. Every reroll, rebuild or edit
  writes the next free `v<n+1>` beside it; versions are never overwritten or evicted.
- Each version's sidecar has a `version` block (`n`, `parent`, `changed`, `how`); an edit adds an
  `edit` block (`text`, `ops`, `interpreter`, `notes`, `affected`).
- `GET /api/zones/{zone}/versions` lists them. The page's header steps through them (◂ v2 ▸) and
  names each one's parent and what changed.
- **Undo** opens the parent version and **redo** the newest child, on the page, with no server
  call. An edit typed against an older version branches from it.

## Rebuilds ([`generators/rebuild.py`](../../../generators/rebuild.py), `POST /api/rebuild`)

A rebuild starts from the parent's saved inputs: `<name>.spec.json`, `<name>.request.json`, the
TER and textures inside its `.eqg` (`SavedStages`), and the sidecar's texture modes.

| Change | How it's built |
|---|---|
| New `decor_seed`, or one room's own decor seed (room view "Use in zone") | **Partial**: texture drawing is skipped and everything after it runs (Sites, trees, Decor, ZON, Pack, sidecar, GLB); the gate re-checks only what changed against the parent's kept result (`shell_report`) |
| New `rooms_seed` or `seed` | Full build |

A partial rebuild must equal a full build of the same request and seeds byte for byte, footer
aside ([`tests/test_partial_rebuild.py`](../../../tests/test_partial_rebuild.py) per zone type). A room's own decor seed changes only that
room. A pinned decor seed that fails the gate is reported, never rerolled.

## Edits (`POST /api/edit`, `main.py --edit`)

```
 text ──► ai/llm_edits.get_edit_interpreter ──► ops (validated against ai/edits.OPS)
                 (LLM if a key is set, else RuleEditInterpreter)
 ops  ──► generators/edits.apply_edits(saved spec) ──► new spec + affected set
      ──► rebuild.build_spec ──► generate_validated (same gates) ──► v<n+1>
```

| Op | Applied |
|---|---|
| `set_purpose`, `add_lock`, `remove_lock` | yes (locks through the layout's own gating rule, so the result stays solvable) |
| `reroll_room`, `reroll_decor`, `set_decor_level`, `regenerate` | yes |
| `widen_room`, `narrow_room`, `taller_room`, `lower_room` | yes ([`generators/resize.py`](../../../generators/resize.py), clamped, the share applied named); not on outdoor dungeons |
| `add_room`, `remove_room`, `add_region`, `remove_region`, `set_verticality`, `set_topology` | recognised, answered "not yet supported" |

An edit that can be built from the parent's stages is built that way (a partial rebuild); otherwise it builds in full.
The answer is `applied: false` (with HTTP status 200) when nothing was built: no ops (with help text), invalid ops, every
op rejected, or every candidate failing the gate; nothing on disk changes. One build per zone runs at
a time; a second request gets HTTP 429 (too many requests). An edit outside the quality bands is still built and marked
`edit_outside_bands`.

## On the page

[`web/src/feedback.ts`](../../../web/src/feedback.ts): the Feedback box, the ops it got, notes, and a tint over the affected
rooms (graph rooms fill their outline; classic and city rooms get a disc; corridors aren't
tinted).
