"""
generators/pipeline.py
----------------------
The validated generation pipeline: bake the traversability validator (and, from
wave 6, the Format_Checker) into the hot path so a client is never shown a zone
that fails either gate, and no rejected attempt is ever left on disk.

    spec_factory(seed) -> ZoneSpec
         |
         v   (each attempt builds into a per-attempt SCRATCH dir)
    build (ZoneBuilder)  ->  validate (traversability + corridor continuity)
         |                        + fmt (Format_Checker; passing STUB until 20.3)
         |                         |
         |  pass                   |  fail (gated theme, random seed)
         v                         v
    move scratch -> v<version>  log JSONL + rmtree scratch, fresh seed + retry
         |                         |   (bounded by attempt cap AND timeout)
         v                         v  budget exhausted
    ValidatedBuild            GenerationFailed  (+ JSONL triage log)

This is the single guarantee shared by the Server (`/api/generate`) and the CLI
(`main.py generate`): on a gated zone type, a gate-failing zone is never
returned; on exhaustion the caller gets a typed failure instead of a broken
zone; and — the invariant Property 2 (task 15.6) asserts — a *returned* build's
files live only in ``output_dir/<zone_id>/v<version>/``, while a *rejected*
attempt leaves nothing behind (no ``.attempts`` entry, no build directory).

The validator (`analyzer.traverse.validate`) stays a pure pass/fail; the
scratch-attempt lifecycle, retry / timeout / logging orchestration lives here,
on top of it.

Zone-type scope: a zone type is *gated* (its builds must pass the
traversability + continuity gate) iff it is in ``gated_zone_types``, which
defaults to ``ENABLED_ZONE_TYPES`` — the one Enabled set (wave 4, Req 3.1);
there is no separate "gated" set any more. Wilderness is DEFINED but DISABLED
in M1, so it is not in the Enabled set and simply isn't offered. A non-gated
build (zone type outside the gated set, or ``validate_enabled=False``) runs
ONCE through the same scratch->move path, marked ``validated=False``.

Filesystem note: this module uses plain ``pathlib`` / ``os`` / ``shutil`` calls
for now. Task 19.5 routes every write, move and remove through ``OutputRoot``
(file-system confinement, wave 6); until then the paths are built directly.
"""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Collection, List, Optional, Sequence

from analyzer.traverse import AgentModel, TraversalReport, validate
from generators.builder import BuildResult, ZoneBuilder
from generators.zone_spec import ZoneSpec
from generators.zone_types import ENABLED_ZONE_TYPES

logger = logging.getLogger("eq_s3d.pipeline")

# ---------------------------------------------------------------------------
# Defaults (product choices; see design.md "Pipeline")
# ---------------------------------------------------------------------------

# Per-zone-type wall-clock budget. A dungeon/city build is sub-second, so a
# small budget finds a good sibling seed fast; wilderness is heavier (deferred
# anyway). ``timeout_s=None`` resolves to DEFAULT_TIMEOUT_S[zone_type].
DEFAULT_TIMEOUT_S = {"dungeon": 20.0, "city": 20.0, "wilderness": 60.0}

# Fallback budget for a zone type with no DEFAULT_TIMEOUT_S entry.
_FALLBACK_TIMEOUT_S = 20.0

# A small attempt budget finds a good sibling seed fast; the timeout guards
# pathological runs. Whichever cap hits first wins.
DEFAULT_MAX_ATTEMPTS = 8

# Append-only JSONL triage feed — one line per rejected attempt. The data a
# future corridor/format triage pass consumes to measure and prioritise fixes.
DEFAULT_FAILURE_LOG = Path("output") / "validation_failures.jsonl"


# A factory that, given a seed, produces a fresh ZoneSpec for that seed. The
# pipeline owns the seed-selection loop and calls this once per attempt.
SpecFactory = Callable[[int], ZoneSpec]


# ---------------------------------------------------------------------------
# Format_Checker stub (real one lands in task 20.3)
# ---------------------------------------------------------------------------
#
# The design's step 2 runs `fmt = check_eqg(eqg, spec, sidecar_path=...)` and the
# PASS criterion is `report.passed AND report.corridors_passed AND fmt.passed`.
# The real Format_Checker (`analyzer/rof2check.py`, FormatReport) is wave 6 /
# task 20.3. Until then, so waves 4 and 6 stay separable, `fmt` is a clearly
# marked STUB that ALWAYS passes with an empty check list and a `to_dict()` of
# the same shape the real FormatReport.to_dict() will produce
# ({"passed", "checks"}). Task 20.3 replaces `_format_check_stub` with the real
# `check_eqg` call; nothing else in this module changes.

@dataclass
class _FormatStub:
    """Passing Format_Checker stand-in. Replaced by FormatReport in task 20.3."""
    passed: bool = True
    checks: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        # Same shape the real FormatReport.to_dict() produces (design "#### Format_Checker").
        return {"passed": self.passed, "checks": list(self.checks)}

    @property
    def failed_checks(self) -> List[str]:
        """Names of the failed checks (empty while this is a passing stub)."""
        return []


def _format_check_stub(eqg_path, spec, sidecar_path) -> _FormatStub:
    """STUB for the wave-6 Format_Checker. Always passes. (task 20.3 replaces me.)"""
    return _FormatStub(passed=True, checks=[])


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
    # Names of the gates/checks this attempt failed, e.g. ["traversability",
    # "corridor_continuity"] or Format_Checker check names once 20.3 lands. This
    # is what the JSONL `checks` field and the GenerationFailed message list.
    checks: List[str] = field(default_factory=list)


@dataclass
class ValidatedBuild:
    """A passing (or intentionally ungated) build plus provenance for callers."""
    result: BuildResult
    spec: ZoneSpec
    seed: int                    # the seed that actually produced this zone
    attempts: int                # how many builds it took (1 on first-try/ungated)
    validated: bool              # did the traversability gate run AND pass?
    gated: bool                  # was this zone type in the gated set (and validate_enabled)?
    zone_type: str = ""          # the zone type this build is for
    build_dir: Optional[Path] = None  # output_dir/<zone_id>/v<version> — where the files live
    report: Optional[TraversalReport] = None
    format: Optional[_FormatStub] = None   # FormatReport once 20.3 lands
    warnings: List[str] = field(default_factory=list)


class GenerationFailed(Exception):
    """
    No valid zone could be produced within budget, or a pinned seed failed a
    gate (pinned seeds are never silently swapped — we respect the explicit
    request and error out). Carries every rejected attempt — each with the seed
    it used and the checks it failed — so the caller can surface / log them.
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
        # List each rejected seed with its failed checks (Req 4.2 / umbrella 4.7).
        rejected = "; ".join(
            f"seed {f.seed} failed [{', '.join(f.checks) or 'validation'}]"
            for f in failures
        )
        detail = f" — {rejected}" if rejected else ""
        super().__init__(
            f"could not produce a valid '{zone_type}' zone for '{zone_id}' "
            f"({why}){detail}"
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


def _failed_checks(report: TraversalReport, fmt: _FormatStub) -> List[str]:
    """The gate/check names a rejected attempt failed, in gate order.

    ``traversability`` (some room unreachable), ``corridor_continuity`` (a
    corridor floor breaks or two corridors conflict), and the Format_Checker's
    own failed-check names (none while ``fmt`` is the passing stub). This is the
    list that rides in the JSONL ``checks`` field and the GenerationFailed
    message (Req 4.2).
    """
    checks: List[str] = []
    if not report.passed:
        checks.append("traversability")
    if not report.corridors_passed:
        checks.append("corridor_continuity")
    if not fmt.passed:
        checks.extend(fmt.failed_checks or ["format"])
    return checks


def log_validation_failure(failure_log: Optional[str | Path], *,
                           zone_id: str, zone_type: str, seed: int, attempt: int,
                           report: TraversalReport,
                           checks: Sequence[str]) -> AttemptFailure:
    """
    Record one rejected attempt: a structured line to stderr (via ``logging``)
    and an append-only JSONL entry to ``failure_log`` (the triage feed). The
    JSONL line carries the failed ``checks`` list (design step 5). Returns the
    AttemptFailure so the caller can accumulate it for GenerationFailed.
    """
    reasons = _failure_reasons(report)
    failure = AttemptFailure(
        seed=seed,
        attempt=attempt,
        reachable_rooms=report.reachable_rooms,
        total_rooms=report.total_rooms,
        reasons=reasons,
        checks=list(checks),
    )

    logger.warning(
        "gate REJECT zone=%s zone_type=%s seed=%s attempt=%d "
        "reachable=%d/%d checks=%s reasons=%s",
        zone_id, zone_type, seed, attempt,
        report.reachable_rooms, report.total_rooms,
        ",".join(checks) or "(none)",
        "; ".join(reasons) or "(none)",
    )

    if failure_log is not None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "zone_id": zone_id,
            "zone_type": zone_type,
            "seed": seed,
            "attempt": attempt,
            "checks": list(checks),
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
# Scratch-directory lifecycle (plain pathlib for now; OutputRoot in task 19.5)
# ---------------------------------------------------------------------------

def _scratch_dir(output_dir: Path, zone_id: str, k: int) -> Path:
    """Per-attempt scratch directory: ``output_dir/.attempts/<zone_id>/a<k>/``."""
    return output_dir / ".attempts" / zone_id / f"a{k}"


def _move_into(scratch: Path, final: Path) -> None:
    """Move every file from ``scratch`` into ``final`` with ``os.replace``.

    Same volume, so each move is atomic. ``final`` is created fresh; a stale
    ``final`` (e.g. a re-generate of the same zone id + version) is removed
    first so the move can't collide with leftover files.
    """
    if final.exists():
        shutil.rmtree(final)
    final.mkdir(parents=True, exist_ok=True)
    for entry in scratch.iterdir():
        os.replace(str(entry), str(final / entry.name))


def _remove_scratch(output_dir: Path, zone_id: str, scratch: Path) -> None:
    """Remove a scratch attempt dir and the now-empty ``.attempts/<zone_id>`` parent.

    Rejected and accepted attempts both call this (via the callers below) so an
    attempt never leaves a directory behind — the invariant Property 2 asserts.
    Removing the ``.attempts/<zone_id>`` parent when it is empty keeps the
    output directory clean; the ``.attempts`` root is likewise removed when it
    is empty, so a returned build leaves ONLY ``<zone_id>/v<version>/`` (and the
    failure log) behind — the Property 2 invariant. A still-populated
    ``.attempts`` (another zone's in-flight scratch) is left untouched.
    """
    if scratch.exists():
        shutil.rmtree(scratch, ignore_errors=True)
    attempts_root = output_dir / ".attempts"
    for pruned in (attempts_root / zone_id, attempts_root):
        try:
            if pruned.exists() and not any(pruned.iterdir()):
                pruned.rmdir()
        except OSError:
            pass  # a concurrent attempt repopulated it — harmless.


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
    version: int = 1,
    write_glb: bool = True,
    ter_version: int = 2,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    timeout_s: Optional[float] = None,
    gated_zone_types: Optional[Collection[str]] = None,
    validate_enabled: bool = True,
    agent: Optional[AgentModel] = None,
    rng: Optional[random.Random] = None,
    failure_log: Optional[str | Path] = DEFAULT_FAILURE_LOG,
    warnings: Sequence[str] = (),
    planned_zone_type: Optional[str] = None,
) -> ValidatedBuild:
    """
    Build a zone and guarantee (for gated zone types) that it passes the
    traversability + corridor-continuity gate (and, from task 20.3, the
    Format_Checker) before returning it — and that no rejected attempt is left
    on disk.

    ``spec_factory(seed)`` must return a fresh ZoneSpec for the given seed
    (name/zone_type/room-count already applied); the pipeline owns which seed to
    use on each attempt.

    Lifecycle (per attempt *k*, design "Pipeline"):

    * build into a SCRATCH dir ``output_dir/.attempts/<zone_id>/a<k>/``;
    * ``report = validate(eqg, spec, agent, check_corridors=True)`` and
      ``fmt = check_eqg(...)`` (a passing stub until task 20.3);
    * PASS ⇔ ``report.passed ∧ report.corridors_passed ∧ fmt.passed``;
    * on PASS: ``os.replace`` every file into
      ``output_dir/<zone_id>/v<version>/``, merge ``format``/``warnings``/
      ``validated``/``attempts``/``seed`` (and ``planned_zone_type`` when a
      prompt-planned zone type was substituted) into the Sidecar there, remove
      the scratch and its empty parent, and return;
    * on FAIL: log one JSONL line (with the failed ``checks``), ``rmtree`` the
      scratch, then the pinned / attempt-cap / timeout logic;
    * a builder EXCEPTION removes the scratch in a ``finally`` and re-raises.

    Behaviour by scope:

    * **Ungated zone type** (zone type outside ``gated_zone_types``) or
      ``validate_enabled=False``: build ONCE through the same scratch->move
      path and return it marked ``validated=False`` (no retries, so no false-fail
      retry storm).
    * **Gated, random seed**: build -> gate -> on failure pick a NEW fresh seed
      and retry, bounded by ``max_attempts`` AND ``timeout_s`` (whichever hits
      first). At least one full attempt always completes. Returns the first
      passing build; raises :class:`GenerationFailed` when the budget is spent.
    * **Gated, pinned seed**: build -> gate once. On failure raise
      :class:`GenerationFailed` (``pinned=True``) rather than silently swapping
      the caller's explicit seed.
    """
    if zone_type is None:
        raise TypeError("generate_validated() requires zone_type")
    output_dir = Path(output_dir)
    if gated_zone_types is None:
        gated_zone_types = ENABLED_ZONE_TYPES
    if timeout_s is None:
        timeout_s = DEFAULT_TIMEOUT_S.get(zone_type, _FALLBACK_TIMEOUT_S)

    gated = validate_enabled and zone_type in set(gated_zone_types)
    pinned = seed is not None
    base_warnings = list(warnings)
    final_dir = output_dir / zone_id / f"v{version}"

    # -- Ungated / validation-disabled: single build through the scratch path.
    if not gated:
        use_seed = seed if pinned else _fresh_seed(rng)
        scratch = _scratch_dir(output_dir, zone_id, 1)
        try:
            spec = spec_factory(use_seed)
            result = ZoneBuilder(spec).build(
                output_dir=scratch, write_glb=write_glb, ter_version=ter_version,
            )
            # Ungated builds still run the Format_Checker and record it.
            fmt = _format_check_stub(result.eqg_path, spec,
                                     scratch / f"{spec.name.lower()}.zone.json")
            all_warnings = base_warnings + list(result.warnings)
            moved = _finalize_build(
                result, scratch, final_dir, fmt=fmt, warnings=all_warnings,
                validated=False, attempts=1, seed=use_seed,
                planned_zone_type=planned_zone_type,
            )
            _remove_scratch(output_dir, zone_id, scratch)
        except Exception:
            # Builder crash: leave nothing behind, re-raise.
            _remove_scratch(output_dir, zone_id, scratch)
            raise

        note = ("validation disabled" if not validate_enabled
                else f"zone_type '{zone_type}' is not in the gated set "
                     f"{sorted(gated_zone_types)}")
        logger.info("ungated build zone=%s zone_type=%s seed=%s (%s); "
                    "returned without the traversability gate",
                    zone_id, zone_type, use_seed, note)
        return ValidatedBuild(
            result=moved, spec=spec, seed=use_seed, attempts=1,
            validated=False, gated=False, zone_type=zone_type,
            build_dir=final_dir, report=None, format=fmt,
            warnings=all_warnings,
        )

    # -- Gated: build -> gate -> retry-on-fresh-seed (random only). ----------
    start = time.monotonic()
    failures: List[AttemptFailure] = []
    attempt = 0

    while True:
        attempt += 1
        use_seed = seed if pinned else _fresh_seed(rng)
        scratch = _scratch_dir(output_dir, zone_id, attempt)
        try:
            spec = spec_factory(use_seed)
            result = ZoneBuilder(spec).build(
                output_dir=scratch, write_glb=write_glb, ter_version=ter_version,
            )
            report = validate(result.eqg_path, spec=spec, agent=agent,
                              check_corridors=True)
            fmt = _format_check_stub(result.eqg_path, spec,
                                     scratch / f"{spec.name.lower()}.zone.json")
            passed = report.passed and report.corridors_passed and fmt.passed

            if passed:
                all_warnings = base_warnings + list(result.warnings)
                moved = _finalize_build(
                    result, scratch, final_dir, fmt=fmt, warnings=all_warnings,
                    validated=True, attempts=attempt, seed=use_seed,
                    planned_zone_type=planned_zone_type,
                )
                _remove_scratch(output_dir, zone_id, scratch)
                if attempt > 1:
                    logger.info("gate PASS zone=%s zone_type=%s seed=%s on "
                                "attempt %d", zone_id, zone_type, use_seed, attempt)
                return ValidatedBuild(
                    result=moved, spec=spec, seed=use_seed, attempts=attempt,
                    validated=True, gated=True, zone_type=zone_type,
                    build_dir=final_dir, report=report, format=fmt,
                    warnings=all_warnings,
                )

            # Rejected — gather the failed checks, log for triage, drop scratch.
            checks = _failed_checks(report, fmt)
            failures.append(log_validation_failure(
                failure_log, zone_id=zone_id, zone_type=zone_type,
                seed=use_seed, attempt=attempt, report=report, checks=checks,
            ))
            _remove_scratch(output_dir, zone_id, scratch)
        except Exception:
            # Builder crash mid-attempt: leave nothing behind, re-raise.
            _remove_scratch(output_dir, zone_id, scratch)
            raise

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


def _finalize_build(result: BuildResult, scratch: Path, final_dir: Path, *,
                    fmt: _FormatStub, warnings: Sequence[str], validated: bool,
                    attempts: int, seed: int,
                    planned_zone_type: Optional[str] = None) -> BuildResult:
    """Move a passing/ungated build out of scratch into ``final_dir``.

    ``os.replace`` every file from ``scratch`` into ``final_dir`` (atomic on the
    same volume), merge the pipeline fields (``format``/``warnings``/
    ``validated``/``attempts``/``seed``, plus ``planned_zone_type`` when a
    substitution occurred) into the Sidecar there, and rewrite the
    BuildResult paths to point at their new home. The scratch directory is
    removed by the caller (so the one ``finally`` cleanup covers both the
    success and failure exits).
    """
    _move_into(scratch, final_dir)

    name = result.spec.name.lower()

    # Rewrite the BuildResult's paths to point at the moved files.
    def _relocate(p):
        return (final_dir / Path(p).name) if p is not None else None

    result.eqg_path = _relocate(result.eqg_path)
    result.glb_path = _relocate(result.glb_path)
    result.sidecar_path = _relocate(result.sidecar_path)
    result.map_path = _relocate(result.map_path)

    # Merge the pipeline provenance into the moved Sidecar. ZoneBuilder already
    # wrote a <name>.zone.json into scratch (and it moved with the rest); we
    # re-read it, add the pipeline fields, and rewrite in place.
    sidecar = final_dir / f"{name}.zone.json"
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data.update({
            "format": fmt.to_dict(),
            "warnings": list(warnings),
            "validated": validated,
            "attempts": attempts,
            "seed": seed,
        })
        # ``planned_zone_type`` appears in the Sidecar only when a prompt-planned
        # zone type was substituted (design "Build naming ... Sidecar additions").
        if planned_zone_type is not None:
            data["planned_zone_type"] = planned_zone_type
        sidecar.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return result
