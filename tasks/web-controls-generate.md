# TASK: web-controls-generate

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Web viewer UX — make the "Controls" panel a first-class, self-contained
      way to drive generation: more parameters exposed as fields, plus its own
      Generate button so it's obviously independent of the top prompt box.
Last touched: 2026-10-18 — task captured.

## Goal

Grow the viewer's **"Controls"** `<details>` panel into a complete manual-driver
for generation and give it **its own Generate button**, so the control-driven
path reads as clearly separate from the prompt-driven one. Today there's a
single top-bar **Generate** button sitting next to the prompt text box; the
Controls dropdown (Theme / Rooms / Elevation / Seed) has no button of its own,
so it's ambiguous whether that top Generate uses the prompt or the controls.
(In fact `doGenerate()` prefers the prompt when it's non-empty and only falls
back to controls when the prompt is blank — a subtlety the UI doesn't surface.)
Done when the Controls panel has a dedicated Generate action that *always*
generates from the control fields (ignoring the prompt), the top Generate
clearly belongs to the prompt, and the panel exposes more of the parameters the
backend already understands.

## Why

The two generation modes (prompt vs. controls) currently share one button and
an implicit "prompt wins if set" rule that isn't visible to the user. Someone
tweaking Theme/Rooms/Seed and hitting the only Generate button can be silently
overridden by leftover prompt text. Splitting the button makes each path
explicit and lets the Controls panel stand on its own as the deterministic,
no-LLM way to drive the generator — which pairs naturally with the seed input
shipped in `web-seed-input` (pin a seed + pick exact theme/rooms = fully
reproducible manual generation).

## What already exists (so scope stays small)

- `web/index.html`: top bar has `#prompt` (text) and `#generate` (button); the
  `#advanced` `<details>` "Controls" panel already holds `#theme`, `#rooms`,
  `#elevation`, and `#seed` (added by `web-seed-input`).
- `web/src/main.ts` `doGenerate()`: reads prompt + all control fields, and
  branches — **if the prompt is non-empty it drives generation and the controls
  are ignored; only a blank prompt falls through to the control fields.** The
  seed is threaded into both param objects.
- `server/app.py` `GenerateRequest`: accepts `prompt`, `theme`, `rooms`
  (1–30), `elevation`, `seed`. When `prompt` is set the planner derives
  theme/rooms and the explicit fields are ignored server-side too.

So the front-end work is mostly: a second Generate button scoped to the
controls, a `doGenerate()` that can be told "controls only, ignore the prompt",
and wiring new fields through the existing param object. New *fields* beyond
what the backend already accepts (see open question) would need matching
`GenerateRequest` additions.

## Open question for the user (resolve before building)

"More fields" is underspecified — the backend's control path currently only
takes theme/rooms/elevation/seed. Candidate additions, roughly in order of how
cheaply they map to existing backend capability:

- **Keyed / gates toggle** — whether to request a lock-and-key dungeon (the
  response already reports `gates`; needs a request flag + plumb into the
  layout/gating step).
- **Size** (small/medium/large) and **verticality** (flat/moderate/vertical) —
  these already exist as `ZonePlan` concepts on the prompt path; exposing them
  on the control path means `LayoutGenerator` must accept them directly.
- **Room-count already exists** (`#rooms`); could add min/max corridor length,
  multi-level/levels (ties into `tasks/multi-level-dungeon.md`), etc.

Decide the field set with the user first; don't invent backend parameters
speculatively (ROADMAP: layouts are suggestions, keep the IR clean).

## Acceptance criteria

- [ ] The Controls `<details>` panel contains its **own Generate button** (e.g.
      `#generate-controls`) that generates **from the control fields only**,
      explicitly ignoring any text in `#prompt`.
- [ ] The top-bar `#generate` button is clearly the **prompt** action (label /
      grouping / tooltip make it read as "generate from the description"); the
      two buttons are visually distinct and it's obvious which drives which.
- [ ] `doGenerate()` is refactored to take an explicit mode (prompt vs.
      controls) rather than inferring it from whether the prompt is blank, so
      the controls button never gets overridden by stale prompt text and the
      prompt button never silently uses the controls.
- [ ] The agreed set of **additional fields** (see open question) is present in
      the Controls panel, wired through the param object, and — where it needs
      backend support — reflected in `server/app.py` `GenerateRequest` and the
      control-driven factory. Each new field round-trips (set it, generate, see
      it honoured in the result/panel).
- [ ] New fields are **keyboard-safe** like the existing ones: inputs/selects
      are already excluded by `controls.ts` `_typingTarget()` and the map-key
      `typing` guard, so WASD/Space/R edit the field instead of moving the
      camera (verify for any non-input control type added).
- [ ] Empty-seed-is-random behaviour is preserved on the controls path
      (ROADMAP: randomness is a MUST; the seed field is an override, not a new
      default).
- [ ] Works against the built front-end, not just the live build — `web/dist`
      rebuilt; the built `index.html` + bundle carry the new button and fields.
- [ ] Relevant `docs/ACCEPTANCE.md` section(s) updated/confirmed in the viewer
      (human eyeball that both buttons do the right thing and new fields take
      effect).

## Subtasks

- [ ] Confirm the additional-field set with the user (close the open question).
- [ ] `web/index.html`: add a Generate button inside the `#advanced` panel; give
      the top `#generate` prompt-scoped labelling/tooltip. Add the agreed new
      field controls to the panel.
- [ ] `web/src/main.ts`: refactor `doGenerate()` to accept an explicit source
      (`"prompt" | "controls"`); wire the new button to the controls path and
      the top button to the prompt path. Read/parse any new fields into the
      param object.
- [ ] `web/src/api.ts`: extend `GenerateParams` (and `GenerateResult` if new
      fields echo back) for any added parameters.
- [ ] `server/app.py`: extend `GenerateRequest` and the control-driven factory
      for any new fields that need backend support; keep the prompt path
      unchanged. Validate ranges so a bad value can't 422 the user.
- [ ] Verify keyboard-safety for any new control types; preserve blank-seed =
      random.
- [ ] Rebuild `web/dist`; update `docs/ACCEPTANCE.md`; eyeball both buttons and
      each new field in the 3D viewer.

## Deliverables

What actually shipped. Fill in as work lands.

- Code (front-end): `web/index.html`, `web/src/main.ts`, `web/src/api.ts`,
  `web/src/style.css` (button/field styling), `web/dist` rebuilt.
- Code (backend, only if new fields need it): `server/app.py`
  (`GenerateRequest` + control factory), possibly `generators/layout.py`.
- Tests: only if a backend parameter warrants one (don't add tests for pure
  front-end wiring).
- Docs: `docs/ACCEPTANCE.md`; this file kept in sync.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Key UX point:** the fix isn't only cosmetic — `doGenerate()` today infers
  mode from "is the prompt blank?", so a controls-only Generate button must pass
  an explicit mode, or leftover prompt text will keep hijacking control-driven
  generation. Make the mode explicit in the refactor, not implicit.
- Pairs with `web-seed-input` (shipped): controls + pinned seed = fully
  reproducible manual generation, no LLM involved.
- Scope guard: resist inventing backend parameters. Only expose fields the
  backend can honour; anything new goes through `GenerateRequest` + the control
  factory deliberately, with range validation.
- Integration note (single-writer tracker rule): when this task lands, the
  `tasks/README.md` board needs a new row — `web-controls-generate` — and its
  status kept in sync there by the integration step, not edited during task
  work.
