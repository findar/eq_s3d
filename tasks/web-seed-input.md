# TASK: web-seed-input

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Web viewer UX / validation support — let a human reproduce a specific
      seed in the 3D view, so seed-specific findings (e.g. the traversability
      validator flagging seed 1955208177) can actually be eyeballed.
Last touched: created after the traversability validator landed; blocks its
      final "3D spot-check" trust step

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

- [ ] A seed input exists in the viewer controls (e.g. in the `#advanced`
      "Controls" panel): empty = random (current behaviour), a number = pin that
      seed. Non-numeric/blank input falls back to random, never errors.
- [ ] Entering a seed and generating produces that exact zone deterministically
      (same seed + same theme/rooms/elevation ⇒ identical geometry); verified by
      generating the same seed twice and getting the same polys/bounds.
- [ ] The panel's shown seed (`#m-seed`) reflects the actual seed used (random
      or pinned), and there's a one-click way to reuse it — either a "copy seed"
      button or a "reproduce last" action that refills the input with the last
      result's seed.
- [ ] Prompt-driven generation still works: a seed can be combined with a prompt
      (planner derives theme/rooms, seed pins the randomness) OR the seed field
      is clearly scoped to control-driven gen — pick one and make it obvious.
      (Server currently applies `seed` in both paths, so combining is cheap.)
- [ ] Typing in the seed field is keyboard-safe like the prompt box: WASD/Space/R
      edit the field and do NOT move the camera (ACCEPTANCE F "Typing is safe").
- [ ] Works against the built front-end, not just dev — `web/dist` rebuilds and
      serves the field (or note the `npm run build` step in the deliverable).

## Subtasks

- [ ] Add a seed `<input type="number">` (or text, parsed) to `web/index.html`
      controls, with a placeholder like "seed (blank = random)". Consider a
      small "⟳ reproduce" button next to the shown seed in the panel.
- [ ] In `web/src/main.ts` `doGenerate()`: read the seed field, parse to a
      number (blank/NaN → omit), and include it in the params object. Keep the
      existing prompt-vs-controls branching; decide + implement seed's role when
      a prompt is set.
- [ ] Wire the "reproduce last / copy seed" affordance: on a result, store
      `result.seed`; the button refills the input (and/or copies to clipboard).
- [ ] Ensure the seed field is in the controls' "don't steal keys while typing"
      set (same handling as `#prompt`) so first-person controls don't fire.
- [ ] Manual check: pin a seed, generate twice, confirm identical; blank it,
      confirm random each time; paste the validator's flagged seed and walk it.
- [ ] Rebuild `web/dist` (`cd web && npm run build`) if the served build is used;
      update `docs/ACCEPTANCE.md` F if a new control deserves a checklist line.

## Deliverables

- Code: `web/index.html` (seed field + reproduce affordance), `web/src/main.ts`
  (read/pass seed, reproduce handler); `web/src/api.ts` already supports it.
- Docs: `docs/ACCEPTANCE.md` (F. Web viewer UX) if a checklist item is added;
  this file. ROADMAP "Web app" / Known-issues note if relevant.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Unblocks `tasks/traversability-validator.md`'s** final step: with seed input
  you can load the exact flagged seed (e.g. 1955208177) and confirm in 3D that
  the rooms the validator calls unreachable really are — the last trust step
  before leaning on the validator for the section-B MUSTs.
- Backend is already seed-capable; resist scope creep into the API. If a backend
  tweak turns out necessary (e.g. returning the seed in an error path), note it
  but keep it minimal.
- Determinism caveat to verify: confirm that pinning the seed alone reproduces a
  zone given the same theme/rooms/elevation. Some backends derive sub-seeds from
  the zone *name* (which is a timestamped `gen_...` id) — check that geometry is
  seeded from the user seed, not the name, or the "same seed ⇒ same zone"
  guarantee won't hold. If it's name-derived anywhere, that's a real finding to
  log (and possibly a small fix) rather than paper over.
- Keep the "empty = random, identical inputs still vary" behaviour (ROADMAP:
  randomness is a MUST) — the seed field is an override, not a new default.
