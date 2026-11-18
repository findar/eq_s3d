# Design — zone-generator-edits (roadmap step 18)

Written at master `bac2371`. Verify each section against the code before building on it.

## Shape

```
text ──RuleEditInterpreter──▶ ops ──validate──▶ ops'                       (ai/edits.py)
                                      │
parent v<n>/<name>.spec.json ──apply_edits(doc, ops', seed)──▶ doc', affected, notes, how
                                      │                                    (generators/edits.py)
                       how == partial ▼                       how == full
           rebuild.py: parent's stages + doc'          generate_validated(factory(doc'))
                                      └──────────▶ v<n+1>/ (+ sidecar `edit` block)
                                                                           (server/app.py)
```

An edit is a rebuild whose change is a list of ops instead of one seed. It reuses
`generators/rebuild.py`: `saved_spec`, `saved_stages`, the factory that loads a spec dict per
attempt, and `generate_validated`'s `stages`, `request`, `version_meta`. A partial edit that
turns out to change the TER is caught by the build's `StaleStages` and retried as full (the
route, not the engine, decides this), so `how` is always honest.

## Ops (`ai/edits.py`)

`EditOp` is a dict `{op, target?, ...}`. `OPS` maps each op to its parameter ranges, for
example `widen_room: {target, by: (0.1, 1.0)}` (fraction of the room's width),
`set_purpose: {target, type: <a known room type>}`, `add_lock: {target}` (the room whose way in
gets a lock), `set_decor_level: {level: none|sparse|normal|dense}`. `validate(ops, spec_doc)`
returns `(good, bad)`: good ops clamped and with their targets resolved to room ids; bad ones
with reasons.

Targets: room id first; then pacing role words (`boss`, `climax`, `final` → `climax`;
`entrance`, `start` → `entrance`; `hub`; `dead end` → `deadend`); then a room type or rule-set
kind (`crypt`, `barracks`, `chamber`). Ordinals ("the second hub") are out.

`RuleEditInterpreter` is phrase rules over the cleaned text: verb groups ("bigger", "wider",
"larger" → `widen_room`; "taller", "higher ceiling" → `taller_room`; "make X a Y" →
`set_purpose`; "lock", "add a lock to" → `add_lock`; "new decor", "redecorate" →
`reroll_decor` or `reroll_room`; "more/less decor", "sparse" → `set_decor_level`; "start over",
"regenerate" → `regenerate`), each with a target phrase. Several clauses split on "and", ",",
";", "then". Unknown text gives no ops. Its tests are Hypothesis over 0–2000 character strings
plus a table of phrases. `LLMEditInterpreter` mirrors `ai/llm_planner.py`'s key and fallback
handling and is optional (task 6).

## Applying (`generators/edits.py`)

`apply_edits(doc, ops, seed) -> EditResult(doc, affected_rooms, affected_corridors, notes, how,
changed)`. It deep-copies the dict and touches only:

| op | spec change | how |
|---|---|---|
| `set_purpose` | the room's `semantic_type` | partial |
| `reroll_room` | `room_decor_seeds[room]` from a seed derived from (seed, version, op index) | partial |
| `reroll_decor` | `decor_seed`, clearing `room_decor_seeds` (step 16's rule) | partial |
| `set_decor_level` | `decor` | partial |
| `add_lock` / `remove_lock` | `gates`, through the gating code (`layout.py` `_apply_gating`'s solvability rule, lifted to a function both call) | partial unless the door models change the TER |
| `regenerate` | — (a full rebuild of the parent's request with fresh seeds) | full |
| resize ops | task 2 decides | full |

A random draw an op needs comes from `random.Random(f"{seed}:{version}:{i}")` so the same edit
of the same version gives the same result (umbrella 19.1) and a retry (Req 3.4) takes the next
salt.

## Route (`server/app.py`)

`POST /api/edit` beside `POST /api/rebuild`, sharing its parent lookup, its per-zone build lock
(the 429 of Req 3.5) and its version writing. The sidecar gains `edit: {text, ops, interpreter,
notes, affected: {rooms, corridors}}`; `VersionInfo` gains `edit` (text and ops) so the listing
shows it. `applied: false` paths return before any build starts, or after a failed build has
removed its scratch, as Generate's do.

## Page (`web/src/`)

A Feedback section in the side panel (new `web/src/feedback.ts`, as `exportrow.ts` is): text
field, Apply, notes, Undo, Redo. Undo/Redo use the version listing's `parent` fields (already
served). The highlight tints the Affected_Set rooms' floors in the scene (rooms are known by id
in the sidecar's room records).

## Resize (task 2, grounding)

A room's box drives its `outline` (drawn against its doors), its `features`, the corridors'
end points and routes, and its elevation band. Task 2 reads `layout.py`, `outline.py`,
`room_layouts.py`, `routing.py` and `geometry.py` and answers: can one room be resized and its
outline, features and touching corridors redrawn from the spec alone, keeping every other room's
and corridor's triangles (umbrella 19.2)? It records the answer as decision 6 in `archive.md`
with the functions to call; task 7 builds it if the answer is yes, else the ops stay "not yet
supported".
