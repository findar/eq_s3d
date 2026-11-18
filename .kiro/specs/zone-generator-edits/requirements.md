# Requirements Document

> **STATUS: roadmap step 18, DONE** (closed 2026-11-18; the acceptance pass skipped at the user's
> word, so nothing was walked in person; see `archive.md`). Drafted 2026-11-18 at master `bac2371`. The user chose
> "Rest of m4" for step 18 (multi-zone worlds wait on the user's review of their design). The
> lead chose the shape below; the user confirms it at the first look (task 9). Task index:
> `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

Step 16 made every reroll the next **version** of the same zone (`output/web/<zone>/v<n>/`),
never overwritten, and the page steps through them (◂ `v3` ▸). The rest of umbrella M4 is
chat edits ("make the boss room bigger"), the rule-based interpreter that turns them into edit
operations, and undo/redo (umbrella Requirements 18–20, and the session parts of 30).

The umbrella wrote M4 around an in-memory Session with its own history, cursor and evictions.
Step 16's versions already are that history, on disk, and they survive a restart. So step 18
builds M4 on the versions: **an edit is one more kind of rebuild**, undo opens the parent
version and redo the newest child. That drops the Session store, its ids and its limits
(amendments A1–A3).

## Amendments to the umbrella

- **A1 — The history is the zone's versions.** No Session store: an accepted edit writes the
  next version beside its parent, as a rebuild does (decision 35), with its edit recorded in the
  sidecar. Nothing is held only in memory, nothing is evicted and nothing is deleted, so
  umbrella 18.1's session creation, 20.1's discarding of redo entries, 20.8–20.10 and 30.4–30.6,
  30.8, 30.12, 30.13 are dropped. An edit made from an older version branches: its parent is
  that version.
- **A2 — Undo and redo walk the parent links.** Undo opens the open version's parent; redo
  opens the newest version whose parent is the open one. Both are the page's (they change no
  file), so umbrella 20.2–20.4's server round trip becomes opening that version, which already
  loads its own files byte for byte.
- **A3 — The vocabulary grows in two stages.** This step applies the ops the saved spec can
  take without planning the layout again: `set_purpose`, `add_lock`, `remove_lock`,
  `reroll_room`, `reroll_decor`, `set_decor_level` and `regenerate`. The resize ops
  (`widen_room`, `narrow_room`, `taller_room`, `lower_room`) land in this step only if task 2's
  grounding finds a sound way to redraw one room and its corridors; otherwise they, `add_room`,
  `remove_room`, `add_region`, `remove_region`, `set_verticality` and `set_topology` are named
  as recognised but not yet applied ("not yet supported", never a silent no-op).

## Glossary

- **Edit_Op**: one operation, `{op, target?, ...params}`, from the vocabulary of Req 1.
- **Edit**: the ops of one request, with the text they came from (if any), the interpreter's
  name, the notes, and the Affected_Set.
- **Affected_Set**: the room and corridor ids an edit changed.
- **Parent / child**: as step 16: the version an edit started from, and a version made from it.

## Requirements

### Requirement 1: Edit ops and the rule interpreter

1. The vocabulary is umbrella 18.2's. Each op has a schema (its parameters, each with an
   inclusive range); validation clamps a value into its range and rejects an unknown op or a
   missing parameter with a reason.
2. A target resolves against the version's saved spec by room id, by pacing role ("boss room",
   "climax", "entrance", "hub", "dead end"), or by room type / rule-set kind. Several rooms is
   an ambiguous target: rejected with a note listing them. None is rejected with a note naming
   the op and target (umbrella 18.5); the other ops still apply.
3. `RuleEditInterpreter.interpret(text, spec)` returns `(ops, notes, name)` for any string of
   0–2000 characters (empty, whitespace, any Unicode) and never raises. Text is first stripped of
   control characters except newline and tab, then cut to 2000 characters (umbrella 30.9).
4. The interpreter is deterministic: the same text and spec give the same ops.
5. Where an LLM key is configured, an LLM interpreter may be used; its output is accepted only
   as JSON matching the op schema, re-validated and clamped, and the rule interpreter is used on
   any error, a schema failure or no answer within 15 s (umbrella 18.7). Without a key nothing
   changes (umbrella 28).

### Requirement 2: Applying an edit

1. `apply_edits(spec_doc, ops, seed)` returns `(new_doc, affected, notes, how)` and leaves its
   input equal to before (umbrella 19.10). The same inputs give the same outputs (19.1).
2. `set_purpose` changes one room's type; `reroll_room` its decor seed (step 16's room decor
   seed); `reroll_decor` the zone's decor seed; `set_decor_level` the decor control; each has an
   Affected_Set of that room (or every room for the zone-wide ones) and no corridor.
3. `add_lock` and `remove_lock` change the spec's Gates through the gating code's solvability
   rule (a key always before its lock); their geometric Affected_Set is empty (umbrella 19.3).
   A lock that can't be placed solvably is rejected with a note.
4. `regenerate` is a full rebuild with a fresh seed (step 16's reroll rooms, seeds changed).
5. `how` is `"partial"` when the parent's TER is reused (step 16's saved stages) and `"full"`
   otherwise; whichever it is, the version is byte-identical (footer aside) to a full build of
   the edited spec.
6. Every surviving room and corridor keeps its id (umbrella 19.6).
7. The resize ops follow task 2's decision (A3). If they land: a resize that would overlap a
   neighbour is clamped to the largest size that doesn't, and the notes give the requested and
   applied sizes (19.4); rooms and corridors outside the Affected_Set keep their triangles (19.2).

### Requirement 3: The edit route

1. `POST /api/edit {zone, version, text? | ops?}` makes the next version from `version`. With
   `text` the interpreter runs; with `ops` they are validated without it (umbrella 18.3). Ids
   and paths go through `_safe_segment` and `core/paths` as every route does.
2. It answers `applied: true` with the new version, the ops, the notes and the Affected_Set
   (umbrella 19.12); or `applied: false` with a help message (no ops, 18.4), the invalid ops
   and their reasons (18.9), the rejection notes (18.10), or the gate's diagnostics (19.9). On
   `applied: false` no folder is written and nothing on disk changes.
3. The new version's sidecar has step 16's `version` block (`how` from Req 2.5, `changed` naming
   what the ops changed) and an `edit` block: `{text, ops, interpreter, notes, affected}`.
   `GET /api/zones/<zone>/versions` lists each version's edit text and ops.
4. A randomised op (`regenerate`, `reroll_*`) whose candidate fails the gate tries the next
   seed, up to 5 candidates, as Generate retries; deterministic ops build exactly one candidate
   (umbrella 19.8, 19.11). An edit whose build passes the hard gates but not a quality band is
   accepted and marked Quality_Degraded `edit_outside_bands` (19.7).
5. A second edit on the same zone while one is building gets HTTP 429 and changes nothing
   (umbrella 30.7, per zone instead of per Session).
6. The CLI gets `--edit <zone> <version> "<text>"` (same path).

### Requirement 4: The page

1. A Feedback box in the side panel (shown when a build is open): a text field and Apply.
   Apply sends the text against the open version and opens the new version; the response's
   notes show under the box, and `applied: false` keeps the open version and shows why.
2. **Undo** opens the open version's parent; **Redo** the newest child of the open version
   (A2). Undo is disabled on a version with no parent, Redo on one with no child.
3. The Version row names an edit's text, and the version listing in the header's tooltip
   shows each version's edit.
4. After an accepted edit the Affected_Set rooms are highlighted in the 3D view until the next
   edit, undo, redo or version change (umbrella 18.11).
5. Typing in the Feedback box never moves the camera (lessons-learned "movement keys").

### Requirement 5: Unchanged

1. Generate, the CLI's generate, every rebuild and every golden are byte-identical to before.
2. An edit never changes another version's files.
