# TASK: validate-in-pipeline

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Validation tooling — close the loop: a client is never shown a zone that
      fails the traversability validator; failures time out gracefully and are
      logged for triage.
Last touched: created after the traversability validator landed (commit 7aa36ff)

## Goal

Bake the traversability validator into the generation pipeline so an invalid
zone (a room unreachable on foot) is never served to a client. On each
generation, after the build, run the validator; if it fails, **regenerate with a
fresh seed** and retry — bounded by an attempt cap AND a wall-clock timeout. If
no valid zone is produced within budget, return a clean error to the caller
(don't serve the broken zone) and **log the failing seeds + reasons** to a
structured log for later triage. Expose the guarantee through a shared helper so
both the server (`/api/generate`) and the CLI (`main.py generate`) get it, not
just the web path. Done when a broken seed never reaches the browser, the
endpoint stays responsive under the timeout, and every rejected attempt is
recorded with enough detail to drive `corridor-connection`.

## Why

The validator exists but nothing calls it in the hot path — a broken zone ships
straight to the client today. The breakage is seed-dependent (same-axis /
elevation corridor bugs), so most failing seeds have sibling seeds that pass;
silent fresh-seed retry hands the client a good zone without exposing the bug,
while the failure log captures exactly the data `corridor-connection` needs to
measure and prioritise fixes.

## Design (carried from the planning discussion)

- **Generate → validate → retry on fresh seed**, bounded by `max_attempts` AND
  `timeout_s` (whichever hits first). A dungeon build is sub-second, so a small
  budget finds a good seed fast; the timeout guards pathological runs.
- **Shared helper, not server-only.** Add a `generate_validated(...)` entry
  (e.g. in `generators/builder.py` or a new `generators/pipeline.py`) that does
  build + validate + retry + log and returns the first passing `BuildResult`
  (or raises a typed failure). The server and CLI both call it.
- **Validator stays a pure pass/fail**; the retry/timeout/logging orchestration
  is the new layer on top.
- **Theme scope: dungeon-only gate for now.** The validator is only sound for the
  box/dungeon backend; outdoor/cave are in a different coordinate frame (ROADMAP
  Known issue), so gating them would reject every zone → infinite retry →
  timeout. Non-dungeon themes pass through UNVALIDATED (with a logged note that
  they're ungated) until the coordinate-frame fix / cavify rebuild lands. Make
  the gated-theme set explicit and configurable.
- **Pinned seed vs random:** if the caller pins a seed and it fails validation,
  **error out** (respect the explicit request; don't silently swap their seed).
  Only retry-with-fresh-seeds when the seed was random. (Confirm with user.)
- **Structured failure log:** append-only JSONL (e.g.
  `output/validation_failures.jsonl`), one line per rejected attempt:
  timestamp, zone_id, theme, seed, attempt #, reachable/total, and the per-room
  failure reasons from `TraversalReport`. Plus a `logging` line to stderr. This
  is the triage feed.

## Open decisions (confirm with user before building)

- [ ] Budget defaults: `max_attempts` (proposed **8**) and `timeout_s` (proposed
      **20s**), whichever first. OK or adjust?
- [ ] Pinned-seed-fails behaviour: **error** (proposed) vs retry-anyway.
- [ ] Non-dungeon themes: pass-through-ungated (proposed) vs also-gate-once-fixed.
- [ ] Log location/format: `output/validation_failures.jsonl` (proposed).
- [ ] Client-facing error shape on exhaustion: HTTP 503 + a friendly
      "couldn't produce a valid zone, try again" message (proposed).

## Acceptance criteria

- [ ] A shared `generate_validated(...)` helper: builds, runs
      `analyzer.traverse.validate`, retries on a fresh seed for the gated themes,
      bounded by attempt cap + timeout; returns the first passing result or
      raises a typed `GenerationFailed` carrying the attempts/reasons.
- [ ] `/api/generate` uses it: a validator-failing dungeon seed is never
      returned; on exhaustion the client gets a clean error (not a broken GLB).
      A passing zone is returned transparently (response unchanged on success,
      possibly with attempt count / validated flag added).
- [ ] `main.py generate` uses the same helper (so the CLI guarantee matches the
      server). A `--no-validate` / `--allow-invalid` escape hatch exists for
      debugging broken seeds on purpose.
- [ ] Timeout works: a run that can't find a valid zone returns within
      ~`timeout_s` and does not hang the request/process.
- [ ] Every rejected attempt is logged to the structured failure log with
      seed + theme + per-room reasons; verified by forcing failures (low
      `max_attempts`, known-bad theme/seed) and inspecting the log.
- [ ] Dungeon-only gating is explicit; non-dungeon themes pass through ungated
      with a logged note (no false-fail retry storms on outdoor/cave).
- [ ] Pinned-seed-fails behaves per the confirmed decision (error vs retry).
- [ ] Tests (`tests/test_pipeline.py` or extend existing): helper returns a
      passing result when one exists; errors on exhaustion; respects the
      timeout; writes a failure log line; honours the pinned-seed rule; CLI
      `--no-validate` bypasses. Keep them fast (small room counts, tiny budgets).
- [ ] Full suite green.
- [ ] Docs: ROADMAP (validator now gates the pipeline), `docs/ACCEPTANCE.md`
      (note the server self-rejects invalid zones), README if it describes the
      generate flow; this file.

## Subtasks

- [ ] Confirm the open decisions above with the user.
- [ ] Implement `generate_validated(...)` (build + validate + fresh-seed retry +
      timeout + JSONL logging + typed failure). Keep `ZoneBuilder.build` and
      `analyzer.traverse.validate` unchanged underneath.
- [ ] Wire `/api/generate` to it; map exhaustion → clean HTTP error; keep the
      success response shape stable (optionally add `attempts`/`validated`).
- [ ] Wire `main.py generate` to it with a `--no-validate` escape hatch.
- [ ] Structured failure logging helper (append JSONL + stderr `logging`).
- [ ] Tests + full suite green.
- [ ] Docs synced.

## Deliverables

- Code: `generators/builder.py` or new `generators/pipeline.py`
  (`generate_validated`, `GenerationFailed`); `server/app.py` and `main.py`
  wiring; a small logging helper.
- Tests: `tests/test_pipeline.py` (or extensions).
- Docs: ROADMAP, `docs/ACCEPTANCE.md`, README (generate flow); this file.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Depends on the validator** (`tasks/traversability-validator.md`, done) and is
  tightened by **`tasks/corridor-connection.md`**: until corridor fixes land, a
  real fraction of dungeon seeds fail, so retry will do actual work (and the
  failure log will be busy — that's the point, it feeds the fix). After
  corridor-connection, failures should become rare and the log near-empty.
- **Interacts with the cave tasks:** once `cave-cavify-dungeon` makes caves share
  the box coordinate frame and pass the validator, extend the gated-theme set to
  include cave. Outdoor stays ungated until its coordinate-frame issue is fixed.
- **Blocker:** the open decisions (budgets, pinned-seed behaviour, log format,
  error shape) want a user call before implementing — they're product choices,
  not just mechanics.
- Keep randomness intact (ROADMAP MUST): retry picks NEW fresh seeds; it must not
  collapse "identical inputs still vary" — a random request that passes on the
  first try still gets a fresh seed each call.
- Guard the timeout against a slow single build (large room counts): the budget
  is total wall-clock, and at least one full attempt should be allowed to finish
  even if it slightly exceeds, so we never return "failed" without having tried.
