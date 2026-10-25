"""
generators/pipeline.py
----------------------
The validated generation pipeline: bake the traversability validator into the
hot path so a client is never shown a zone that fails it.

    spec_factory(seed) -> ZoneSpec
         |
         v
    build (ZoneBuilder)  ->  validate (analyzer.traverse)
         |                         |
         |  pass                   |  fail (gated theme, random seed)
         v                         v
    ValidatedBuild            fresh seed + retry  (bounded by attempt cap
                                                   AND wall-clock timeout)
         ^                         |
         |                         |  budget exhausted
         +-------------------------+----> GenerationFailed  (+ JSONL triage log)

This is the single guarantee shared by the server (`/api/generate`) and the CLI
(`main.py generate`): on a gated theme, a validator-failing zone is never
returned; on exhaustion the caller gets a typed failure instead of a broken
zone, and every rejected attempt is logged for triage.

The validator (`analyzer.traverse.validate`) stays a pure pass/fail; the
retry / timeout / logging orchestration lives here, on top of it.

Zone-type scope: only zone types whose mesh shares the box / room-graph
coordinate frame can be validated. Wilderness lives in a different frame
(ROADMAP "Known issues"), so gating it would reject every zone -> infinite
retry -> timeout. Non-gated zone types therefore pass through UNVALIDATED (with
a logged note) until the coordinate-frame fix lands. The gated set is explicit
and configurable via ``gated_zone_types``.
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from analyzer.traverse import AgentModel, TraversalReport, validate
from generators.builder import BuildResult, ZoneBuilder
from generators.zone_spec import ZoneSpec

logger = logging.getLogger("eq_s3d.pipeline")

# ---------------------------------------------------------------------------
# Defaults (product choices; see tasks/validate-in-pipeline.md "Open decisions")
# ---------------------------------------------------------------------------

# Zone types whose generated mesh shares the box / room-graph coordinate frame,
# so the traversability validator is sound for them. Dungeon-only until wave 4.
DEFAULT_GATED_ZONE_TYPES = frozenset({"dungeon"})

# A dungeon build is sub-second, so a small budget finds a good sibling seed
# fast; the timeout guards pathological runs. Whichever cap hits first wins.
DEFAULT_MAX_ATTEMPTS = 8
DEFAULT_TIMEOUT_S = 20.0

# Append-only JSONL triage feed — one line per rejected attempt. This is the
# data tasks/corridor-connection.md consumes to measure and prioritise fixes.
DEFAULT_FAILURE_LOG = Path("output") / "validation_failures.jsonl"


# A factory that, given a seed, produces a fresh ZoneSpec for that seed. The
# pipeline owns the seed-selection loop and calls this once per attempt.
SpecFactory = Callable[[int], ZoneSpec]


# ---------------------------------------------------------------------------
# Result / failure types
# ---------------------------------------------------------------------------

@dataclass
class AttemptFailure:
    """One rejected attempt — carried on GenerationFailed and logged to JSONL."""
    seed: int
    attempt: int
    reachable_rooms: int
    total_rooms: int
    reasons: List[str] = field(default_factory=list)  # "<room> [role]: <why>"


@dataclass
class ValidatedBuild:
    """A passing (or intentionally ungated) build plus provenance for callers."""
    result: BuildResult
    spec: ZoneSpec
    seed: int                    # the seed that actually produced this zone
    attempts: int                # how many builds it took (1 on first-try/ungated)
    validated: bool              # did the traversability gate run AND pass?
    gated: bool                  # was this theme in the gated set?
    report: Optional[TraversalReport] = None


class GenerationFailed(Exception):
    """
    No valid zone could be produced within budget, or a pinned seed failed
    validation (pinned seeds are never silently swapped — we respect the
    explicit request and error out). Carries every rejected attempt so the
    caller can surface / log the reasons.
    """

    def __init__(self, zone_id: str, zone_type: str, failures: List[AttemptFailure],
                 *, pinned: bool = False, timed_out: bool = False):
        self.zone_id = zone_id
        self.zone_type = zone_type
        self.failures = failures
        self.attempts = len(failures)
        self.pinned = pinned
        self.timed_out = timed_out
        if pinned:
            why = "pinned seed failed validation"
        elif timed_out:
            why = f"timed out after {self.attempts} attempt(s)"
        else:
            why = f"exhausted {self.attempts} attempt(s)"
        super().__init__(
            f"could not produce a valid '{zone_type}' zone for '{zone_id}' ({why})"
        )


# ---------------------------------------------------------------------------
# Failure logging
# ---------------------------------------------------------------------------

def _failure_reasons(report: TraversalReport) -> List[str]:
    """Per-room failure reasons from the report (only the unreachable rooms)."""
    return [
        f"{r.room_id} [{r.role}]: {r.reason or 'unreachable'}"
        for r in report.rooms
        if not r.reachable
    ]


def log_validation_failure(failure_log: Optional[str | Path], *,
                           zone_id: str, zone_type: str, seed: int, attempt: int,
                           report: TraversalReport) -> AttemptFailure:
    """
    Record one rejected attempt: a structured line to stderr (via ``logging``)
    and an append-only JSONL entry to ``failure_log`` (the triage feed). Returns
    the AttemptFailure so the caller can accumulate it for GenerationFailed.
    """
    reasons = _failure_reasons(report)
    failure = AttemptFailure(
        seed=seed,
        attempt=attempt,
        reachable_rooms=report.reachable_rooms,
        total_rooms=report.total_rooms,
        reasons=reasons,
    )

    logger.warning(
        "traversability REJECT zone=%s zone_type=%s seed=%s attempt=%d "
        "reachable=%d/%d reasons=%s",
        zone_id, zone_type, seed, attempt,
        report.reachable_rooms, report.total_rooms,
        "; ".join(reasons) or "(none)",
    )

    if failure_log is not None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "zone_id": zone_id,
            "zone_type": zone_type,
            "seed": seed,
            "attempt": attempt,
            "reachable_rooms": report.reachable_rooms,
            "total_rooms": report.total_rooms,
            "reasons": reasons,
        }
        p = Path(failure_log)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    return failure


# ---------------------------------------------------------------------------
# Seed selection
# ---------------------------------------------------------------------------

def _fresh_seed(rng: Optional[random.Random]) -> int:
    """A fresh 31-bit seed. Uses the supplied rng (tests) or the module rng."""
    r = rng if rng is not None else random
    return r.randint(0, 2 ** 31 - 1)


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------

def generate_validated(
    spec_factory: SpecFactory,
    *,
    zone_type: Optional[str] = None,
    zone_id: str,
    seed: Optional[int] = None,
    output_dir: str | Path = "output",
    write_glb: bool = True,
    ter_version: int = 2,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    gated_zone_types: Optional[Sequence[str]] = None,
    validate_enabled: bool = True,
    agent: Optional[AgentModel] = None,
    rng: Optional[random.Random] = None,
    failure_log: Optional[str | Path] = DEFAULT_FAILURE_LOG,
) -> ValidatedBuild:
    """
    Build a zone and guarantee (for gated zone types) that it passes the
    traversability validator before returning it.

    ``spec_factory(seed)`` must return a fresh ZoneSpec for the given seed
    (name/zone_type/room-count already applied); the pipeline owns which seed to
    use on each attempt.

    Behaviour:

    * **Ungated zone type** (or ``validate_enabled=False``): build exactly once
      with the pinned seed (or a fresh one) and return it unvalidated, with a
      logged note. No retries, so there is no false-fail retry storm on
      wilderness.
    * **Gated zone type, random seed**: build -> validate -> on failure pick a
      NEW fresh seed and retry, bounded by ``max_attempts`` AND ``timeout_s``
      (whichever hits first). At least one full attempt always completes, so we
      never return "failed" without having tried. Returns the first passing
      build; raises :class:`GenerationFailed` if the budget is exhausted.
    * **Gated zone type, pinned seed**: build -> validate once. On failure raise
      :class:`GenerationFailed` (``pinned=True``) rather than silently swapping
      the caller's explicit seed.

    Every rejected attempt is logged (stderr + JSONL) via
    :func:`log_validation_failure`.
    """
    if zone_type is None:
        raise TypeError("generate_validated() requires zone_type")
    if gated_zone_types is None:
        gated_zone_types = DEFAULT_GATED_ZONE_TYPES

    gated = validate_enabled and zone_type in set(gated_zone_types)
    pinned = seed is not None

    # -- Ungated / validation-disabled: single build, pass through. ----------
    if not gated:
        use_seed = seed if pinned else _fresh_seed(rng)
        spec = spec_factory(use_seed)
        result = ZoneBuilder(spec).build(
            output_dir=output_dir, write_glb=write_glb, ter_version=ter_version,
        )
        note = ("validation disabled" if not validate_enabled
                else f"zone_type '{zone_type}' is not in the gated set "
                     f"{sorted(gated_zone_types)}")
        logger.info("ungated build zone=%s zone_type=%s seed=%s (%s); "
                    "returned without traversability validation",
                    zone_id, zone_type, use_seed, note)
        return ValidatedBuild(
            result=result, spec=spec, seed=use_seed, attempts=1,
            validated=False, gated=False, report=None,
        )

    # -- Gated: build -> validate -> retry-on-fresh-seed (random only). ------
    start = time.monotonic()
    failures: List[AttemptFailure] = []
    attempt = 0

    while True:
        attempt += 1
        use_seed = seed if pinned else _fresh_seed(rng)
        spec = spec_factory(use_seed)
        result = ZoneBuilder(spec).build(
            output_dir=output_dir, write_glb=write_glb, ter_version=ter_version,
        )
        report = validate(result.eqg_path, spec=spec, agent=agent)

        if report.passed:
            if attempt > 1:
                logger.info("traversability PASS zone=%s zone_type=%s seed=%s "
                            "on attempt %d", zone_id, zone_type, use_seed, attempt)
            return ValidatedBuild(
                result=result, spec=spec, seed=use_seed, attempts=attempt,
                validated=True, gated=True, report=report,
            )

        # Rejected — log it for triage and decide whether to retry.
        failures.append(log_validation_failure(
            failure_log, zone_id=zone_id, zone_type=zone_type,
            seed=use_seed, attempt=attempt, report=report,
        ))

        # A pinned seed is an explicit request: don't swap it, error out.
        if pinned:
            raise GenerationFailed(zone_id, zone_type, failures, pinned=True)

        # Budget check AFTER a full attempt, so at least one always finishes
        # (never return "failed" without having actually tried once).
        if attempt >= max_attempts:
            raise GenerationFailed(zone_id, zone_type, failures)
        if (time.monotonic() - start) >= timeout_s:
            raise GenerationFailed(zone_id, zone_type, failures, timed_out=True)
        # else: pick a new fresh seed and retry.
