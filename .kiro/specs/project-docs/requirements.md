# Requirements — project-docs (docs refactor, runs beside step 33)

> **STATUS: ready.** Drafted 2026-11-27 at master `eab72c0`. The user asked how a well-maintained
> project would look at enterprise level ("my own projects at work often times chunk up these types
> of work streams as pillars. each pillar has a plan document outlining the goal, the requirements,
> and then breaking it down into smaller slices and tasks inside"), then: "i also still want to revist the documentation refactor at some point soon so if possible do that in parallel"
> Task index: `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

Docs today are organised by history: 37 step specs frozen at close, `ROADMAP.md` (920 lines, a
13,000-character "Pick up here" line, 25 chained "Carried from step N" lists), `docs/ACCEPTANCE.md`
(4,593 lines), open items scattered over every spec's `archive.md` "Follow-ups", and always-on
steering carrying removed-pipeline notes. The umbrella spec already groups its 33 requirements
into outcome pillars P-A to P-G plus cross-cutting; steps 12-32 drifted almost entirely into P-G and
P-E without anything tracking it.

## Requirements

1. **Pillars.** The umbrella's outcome pillars (P-A Web app and controls, P-B Traversable, P-C
   Usable in RoF2 and EQEmu, P-D True-layout artifacts, P-E EverQuest look and feel, P-F Iterative
   feedback, P-G Engaging every time), plus P-H World (multi-zone, waiting on the user's design
   review) and Engineering (tests, tooling, performance, docs). Each pillar has `PLAN.md` (goal,
   scope and non-goals, requirements with stable IDs, slices with their tasks), `DESIGN.md` (how
   that part works NOW, living), `DECISIONS.md` and `OPEN.md`.
2. **Architecture.** `docs/ARCHITECTURE.md`: the pipeline, the ZoneSpec IR, the module map, the
   data each stage hands on, the north-star rules; component design docs linked from the pillars.
3. **One open-items list.** `OPEN.md` at the root rolls up every pillar's open items, each with its
   source, status (open, parked, waiting on the user) and pillar; every step spec's follow-ups are
   deduplicated against the code (fixed ones dropped, with the commit). Includes the gaps found on
   2026-11-27 (no in-client proof, EQEmu server map/water/nav files, authoring handoff, spawns,
   client performance, `.s3d` era, client art in exports, CI/releases/migrations/user docs,
   failure dashboard).
4. **History kept, findable.** Closed step specs move under the pillar they served as closed
   slices; git history follows the moves. `ROADMAP.md` becomes one page: in flight, next, a line
   per slice with pillar and status, the Done table. `docs/ACCEPTANCE.md` splits per slice with an
   index and the shared checklist.
5. **Steering trimmed.** Always-on `project.md` and `lessons-learned.md` keep what every session
   needs; removed-pipeline notes move to the pillar design they guide. Rules gain: a slice closes
   only when its pillar's `DESIGN.md` describes the new behaviour and its follow-ups are in
   `OPEN.md`.
6. **Tooling follows.** `scripts/task_status.py` reads the new layout and flags follow-ups missing
   from `OPEN.md` and slices not linked from a pillar. A heavy-run lock (`scripts/heavy.py`)
   serialises gate, full and sweep runs across agents.
8. **No `.kiro/`.** The user: "another thing, i want to move away from the .kiro folder structure, so we should try and aim for an agnostic type". Nothing the project needs lives in a tool's folder:
   specs move under their pillar (`docs/pillars/<P-n>/slices/S-<step>-<name>/`, new slices are
   created there); the always-on rules move to a root `AGENTS.md` (the tool-agnostic convention
   many coding agents read) with `CLAUDE.md` reduced to a pointer to it; the lessons move to
   `docs/LESSONS.md` or the pillar DESIGN they guide; the dormant Kiro agent prompts and settings
   move to the Engineering pillar's history. Code comments, tests and scripts that name `.kiro/`
   paths follow. At the end `.kiro/` is gone.
7. **Safe beside live work.** Specs of active steps (32, 33) move last, in the reconcile task, so
   agents working them keep their paths; nothing here changes code behaviour.
