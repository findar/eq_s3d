# TASK: web-seed-input

Status: done        <!-- not-started | in-progress | blocked | done -->
Epic: Web viewer UX / validation support — let a human reproduce a specific
      seed in the 3D view, so seed-specific findings (e.g. the traversability
      validator flagging seed 1955208177) can actually be eyeballed.
Last touched: 2026-10-17 — seed input + reproduce affordance shipped; also fixed
      a determinism bug so cave/outdoor reproduce from the seed (were name-hashed).
      Pending the one human 3D spot-check (walk the flagged seed).

## Goal

Add a **seed input** to the web viewer so you can type (or paste) a specific
seed and regenerate that exact zone, and make the currently-shown seed easy to
copy/reproduce. Today the UI only has theme/rooms/elevation controls and
*displays* the seed after the fact — there's no way to drive a chosen seed, so
seed-specific validation (walking the exact zone the validator flagged) is
impossible from the browser. The backend already supports it end to end (the
API accepts `seed` and echoes it back); this is a front-end-only gap. Done when
you can enter a seed, generate that zone deterministically, see it confirmed in
the panel, and reproduce the last zone with one action.

## Why

This is the missing piece for the **traversability-validator** task's final
acceptance step (a human 3D spot-check of a flagged seed) and for any future
"the validator/test says seed X is broken — go look" workflow. Without seed
input, the only way to view a specific seed is to hand-edit and rebuild locally;
the whole point of the viewer is to not have to do that.

## What already exists (so scope stays small)

- `server/app.py` `GenerateRequest` already has `seed: Optional[int]` and uses
  it when set (`seed = req.seed if req.seed is not None else random.randint(...)`),
  and `GenerateResponse` returns the actual `seed`.
- `web/src/api.ts` `GenerateParams` already declares optional `seed`; the POST
  body is just `JSON.stringify(params)`, so sending a seed needs no API change.
- `web/index.html` already shows the seed in the panel (`#m-seed`), and
  `web/src/main.ts` `doGenerate()` already reads theme/rooms/elevation from the
  controls and logs `result.seed`.

So the work is: a seed field in the controls, read it in `doGenerate()`, pass it
through, and a small "reproduce / copy" affordance. No backend changes expected.

## Acceptance criteria

- [x] A seed input exists in the viewer controls (`#seed`, a `number` field in
      the `#advanced` "Controls" panel): empty = random (current behaviour), a
      number = pin that seed. Blank/non-numeric input falls back to random
      (parsed with `Number`/`Number.isFinite`, negative/decimal floored to a
      non-negative int), never errors.
- [x] Entering a seed and generating produces that exact zone deterministically
      (same seed + same theme/rooms/elevation ⇒ identical geometry); verified by
      generating the same seed twice and getting the same polys/bounds — through
      the server route for all four themes (dungeon/city 332 verts, cave/outdoor
      reproduce too after the determinism fix below).
- [x] The panel's shown seed (`#m-seed`) reflects the actual seed used (random
      or pinned), and there's a one-click "⟳ reproduce" button next to it that
      refills the input with the last result's seed AND copies it to the
      clipboard. Disabled until the first successful generation.
- [x] Prompt-driven generation still works: a seed combines with a prompt
      (planner derives theme/rooms, seed pins the randomness). The server applies
      `seed` in both paths; the front-end includes it in both param objects.
      Verified: `prompt='a big flooded cave' + seed=42` reproduces identically.
- [x] Typing in the seed field is keyboard-safe like the prompt box: it's an
      `<input>`, which `controls.ts` `_typingTarget()` and the map-key handler
      already exclude, so WASD/Space/R edit the field and don't move the camera.
- [x] Works against the built front-end, not just dev — `web/dist` rebuilt via
      `npm run build`; the built `dist/index.html` + JS bundle carry the seed
      field and reproduce button.
- [ ] Human 3D spot-check: paste the validator's flagged seed (1955208177) and
      walk it in the browser to confirm the finding. (Only step needing a human.)

## Subtasks

- [x] Add a seed `<input type="number">` to `web/index.html` controls with a
      "blank = random" placeholder, plus a "⟳ reproduce" button next to the
      shown seed in the panel.
- [x] In `web/src/main.ts` `doGenerate()`: read the seed field, parse to a
      number (blank/NaN → omit), include it in the params object. Seed combines
      with a prompt (both param paths carry it) since the server applies it in
      both.
- [x] Wire the "reproduce last" affordance: store `result.seed` on success; the
      button refills the input and copies to clipboard. Disabled until a result.
- [x] Seed field is keyboard-safe automatically — it's an `<input>`, already
      excluded by `controls.ts` `_typingTarget()` and the map-key `typing` guard.
- [x] Programmatic check: pinned seed generates twice → identical (server route,
      all four themes); blank → random each time; prompt+seed → identical.
- [ ] Human check: paste the validator's flagged seed (1955208177) and walk it
      in 3D to confirm the finding.
- [x] Rebuilt `web/dist` (`npm run build`); added `docs/ACCEPTANCE.md` F lines
      (seed input + extended "typing is safe" to the seed box).
- [x] **Determinism fix (backend finding, see Notes):** thread the user seed
      through `ZoneSpec.seed` so cave/outdoor geometry seeds from the seed, not
      a hash of the timestamped name.

## Deliverables

- Code (front-end): `web/index.html` (seed `#seed` field + `#reproduce`
  button), `web/src/main.ts` (read/parse/pass seed, store `lastSeed`, reproduce
  + copy handler, Enter-to-generate on the seed box), `web/src/style.css`
  (number input + seed-row/button styling). `web/src/api.ts` already declared
  `seed`. `web/dist` rebuilt.
- Code (backend determinism fix): `generators/zone_spec.py` (`ZoneSpec.seed`
  field + serialisation), `generators/layout.py` (`LayoutGenerator` records the
  seed on the spec), `generators/builder.py` (`_base_seed()` prefers the spec's
  seed over a name hash; `_stable_seed()` uses `zlib.crc32` instead of the
  salted builtin `hash()`; applied to the cave, terrain, and texture seeds).
- Docs: `docs/ACCEPTANCE.md` F (seed-input reproduce line + seed box added to
  "Typing is safe"); this file.
- Verification: `python -m pytest tests/ -q` → 179 passed, 3 xfailed. Seed
  reproduces identical geometry for dungeon/city/cave/outdoor (same seed, even
  with different names); server route echoes the seed, random varies when blank,
  prompt+seed combines.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Unblocks `tasks/traversability-validator.md`'s** final step: with seed input
  you can load the exact flagged seed (e.g. 1955208177) and confirm in 3D that
  the rooms the validator calls unreachable really are — the last trust step
  before leaning on the validator for the section-B MUSTs.
- Backend is already seed-capable; resist scope creep into the API. If a backend
  tweak turns out necessary (e.g. returning the seed in an error path), note it
  but keep it minimal.
- Determinism caveat — **CONFIRMED as a real bug and FIXED.** The box backend
  (dungeon/city) already seeded geometry purely from the user seed (via
  `LayoutGenerator`'s RNG), so "same seed ⇒ same zone" held there. But the
  **cave** (`_build_organic`) and **outdoor/terrain** (`_build_terrain`)
  backends in `generators/builder.py` derived their geometry seed from
  `abs(hash(name))` — and `name` is the timestamped, always-unique `gen_...`
  id, so a pinned seed could NEVER reproduce an organic/outdoor zone. Worse,
  Python's builtin `hash()` on strings is salted per-process (PYTHONHASHSEED),
  so cave/outdoor geometry wasn't even stable across server restarts for the
  same name. Fix: added `ZoneSpec.seed`, recorded it in `LayoutGenerator`, and
  made the backends prefer it over the name hash; the remaining hash fallback
  (hand-authored specs with no seed) now uses `zlib.crc32` so it's at least
  stable. Textures seed from the same base seed too. Verified: all four themes
  reproduce identical polys/verts from a pinned seed across different names.
- Keep the "empty = random, identical inputs still vary" behaviour (ROADMAP:
  randomness is a MUST) — the seed field is an override, not a new default.
