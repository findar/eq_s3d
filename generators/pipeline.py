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
         |                        + fmt (Format_Checker; analyzer.rof2check)
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
defaults to ``enabled_zone_types()`` — the one Enabled set (wave 4, Req 3.1)
plus the dev-only wilderness override;
there is no separate "gated" set any more. Wilderness is DEFINED but DISABLED
in M1, so it is not in the Enabled set and simply isn't offered. A non-gated
build (zone type outside the gated set, or ``validate_enabled=False``) runs
ONCE through the same scratch->move path, marked ``validated=False``.

Filesystem note: every write, move and remove is routed through an
``OutputRoot`` (``core/paths.py``) so it is confinement-checked against the
Output_Directory (Req 10.1, task 19.5). The scratch-to-final move uses
``OutputRoot.replace`` and scratch cleanup uses ``OutputRoot.remove_tree`` — the
junction-safe remove that never recurses through a directory junction / symlink
(the lessons-learned ``node_modules`` gotcha, made load-bearing here).
"""

from __future__ import annotations

import inspect
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Collection, Dict, List, Mapping, Optional, Sequence

from analyzer.rof2check import FormatReport, check_eqg
from analyzer.traverse import (
    AgentModel, RoomResult, TraversalReport, load_ter_from_eqg, placed_models, report_with_props,
    shell_report, ter_bytes_from_eqg, validate,
)
from core.paths import OutputRoot
from core.pfs import PfsArchive
from core.ter import TerFile
from generators.builder import BuildResult, SavedStages, ZoneBuilder
from generators.eqmap import build_map_file, prop_marks, site_marks, write_map_files
from generators.mapgeom import extract_outline, outline_summary, with_solids
from generators.mapview import render_map_svg
from generators.rebuild import SHELLS
from generators.outdoor_dungeon import (PLAN_ERRORS, is_outdoor_dungeon,
                                        outdoor_dungeon_report)
from generators.quality import QualityReport, measure, quality_summary
from generators.zone_spec import ZoneSpec
from generators.zone_types import enabled_zone_types

logger = logging.getLogger("eq_s3d.pipeline")

# ---------------------------------------------------------------------------
# Defaults (product choices; see design.md "Pipeline")
# ---------------------------------------------------------------------------

# Per-zone-type wall-clock budget. A dungeon/city build is sub-second, so a
# small budget finds a good sibling seed fast; wilderness is heavier (deferred
# anyway). ``timeout_s=None`` resolves to DEFAULT_TIMEOUT_S[zone_type].
DEFAULT_TIMEOUT_S = {"dungeon": 20.0, "city": 20.0, "wilderness": 60.0,
                     "outdoor_dungeon": 60.0}

# Fallback budget for a zone type with no DEFAULT_TIMEOUT_S entry.
_FALLBACK_TIMEOUT_S = 20.0

# A small attempt budget finds a good sibling seed fast; the timeout guards
# pathological runs. Whichever cap hits first wins.
DEFAULT_MAX_ATTEMPTS = 8

# A whole generate's time budget (district races task 10, archive decision 19). Past the
# zone type's timeout a slow build (a districted giant zone takes 30-170 s an attempt)
# still retries while what has run leaves room for one more of its longest attempt
# inside this, rather than stopping after one. Under the ~5 minute target. Only with
# the default timeout: a caller's own ``timeout_s`` is its whole budget, as before.
DEFAULT_BUDGET_S = 240.0

# Append-only JSONL triage feed — one line per rejected attempt. The data a
# future corridor/format triage pass consumes to measure and prioritise fixes.
DEFAULT_FAILURE_LOG = Path("output") / "validation_failures.jsonl"

# The quality gate (zone-generator-quality Req 3, umbrella 24.5-24.8): an unpinned generate
# may Draw (plan a spec without building it) this many failing specs before it builds the
# lowest-scoring one as degraded. One budget per generate, shared by its attempts.
QUALITY_DRAWS = 32

# The reasons a returned build is marked Quality_Degraded (umbrella 25.2).
REASON_DEGRADED = "quality_degraded"
REASON_PINNED = "quality_outside_bands_pinned"
REASON_EDIT = "edit_outside_bands"


# A factory that, given a seed, produces a fresh ZoneSpec for that seed. The
# pipeline owns the seed-selection loop and calls this once per attempt. One
# that also takes a ``rooms_seed`` keyword (laying the rooms out with it on the
# same World) lets a rooms fault reroll the rooms alone (world-sockets Req 9).
SpecFactory = Callable[..., ZoneSpec]


# ---------------------------------------------------------------------------
# Format_Checker (task 20.3): the real RoF2 format gate
# ---------------------------------------------------------------------------
#
# The design's step 2 runs `fmt = check_eqg(eqg, spec, sidecar_path=...)` and the
# PASS criterion is `report.passed AND report.corridors_passed AND fmt.passed`.
# `check_eqg` (`analyzer/rof2check.py`, FormatReport) is the wave-6 Format_Checker
# — a TOTAL checker that NEVER raises: a bad build becomes a failed attempt with
# named format checks, not a pipeline crash. Its `to_dict()` is the `{"passed",
# "checks"}` block merged into the Sidecar; its `failed_checks` names the checks
# that did not pass, which ride in the JSONL line and GenerationFailed.


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
    # "corridor_continuity"] plus any failed Format_Checker check names
    # (e.g. "diffuse_textures", "safe_point"). This is what the JSONL `checks`
    # field and the GenerationFailed message list.
    checks: List[str] = field(default_factory=list)
    # The stage the gate's report blames (world-sockets Req 9): ``decor``,
    # ``rooms`` or ``zone`` (none named). And the seeds this attempt used:
    # ``seed``, ``rooms_seed``, ``decor_seed``.
    stage: str = ""
    seeds: Dict[str, Optional[int]] = field(default_factory=dict)


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
    format: Optional[FormatReport] = None  # the Format_Checker verdict (rof2check)
    warnings: List[str] = field(default_factory=list)
    # The quality meter's report of the built spec, marked degraded with its reason when it
    # fails the bands; the Sidecar's ``quality`` entry is its ``quality_summary``.
    quality: Optional[QualityReport] = None


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

def _traversal_report(eqg_path: Path, spec: ZoneSpec, agent: Optional[AgentModel], *,
                      reuse: bool = False) -> TraversalReport:
    """The traversability verdict for a built zone.

    Room-graph zones: every room reachable + corridor continuity
    (``analyzer.traverse.validate``). Open wilderness (the spec carries a
    ``wilderness`` payload): the bowl invariant on the shipped mesh — interior
    reachable from Spawn, Rim sealed except at zonelines — as one "bowl" room.
    Outdoor dungeon (a wilderness payload with a dungeon): that bowl room plus
    the dungeon's rooms reached from the outdoor Spawn and its corridors.

    The room gate (room-graph zones and an outdoor dungeon's rooms) is :func:`_room_gate`:
    ``reuse`` (a partial rebuild) judges the Props against a kept shell of this TER when
    there is one. An outdoor dungeon's bowl, and an open wilderness's, always run in full:
    the bowl judges the Sites' Props, which the decor seed places too.
    """
    if is_outdoor_dungeon(spec):
        return outdoor_dungeon_report(eqg_path, spec, agent,
                                      rooms=_room_gate(eqg_path, spec, agent, reuse))
    if spec.wilderness is not None:
        from generators.wilderness.build import bowl_report
        data, name = ter_bytes_from_eqg(eqg_path)
        return bowl_report(spec, TerFile.from_bytes(data, name=name), agent)
    return _room_gate(eqg_path, spec, agent, reuse)


def _room_gate(eqg_path: Path, spec: ZoneSpec, agent: Optional[AgentModel],
               reuse: bool) -> TraversalReport:
    """``validate(eqg_path, spec=spec, agent=agent, check_corridors=True)``, as its two parts
    (``shell_report`` then ``report_with_props``): the same verdict either way. With
    ``reuse`` the shell kept for this TER (``generators.rebuild.SHELLS``) stands in for the
    first part; with none kept it is made and kept for next time. The report's ``shell``
    carries its cache key, so an accepted build can keep it (:func:`_keep_shell`)."""
    arc = PfsArchive.from_file(eqg_path)          # read once, for the TER and the ZON
    data, zone_name = ter_bytes_from_eqg(eqg_path, arc=arc)
    key = SHELLS.key(data, spec, agent)
    shell = SHELLS.shell(key) if reuse else None
    if shell is None:
        shell = shell_report(TerFile.from_bytes(data, name=zone_name), spec, agent, True,
                             zone_name=zone_name)
        shell.key = key
        if reuse:
            SHELLS.keep_shell(key, shell)
    placed = placed_models(eqg_path, arc=arc) if shell.seed_face is not None else ()
    return report_with_props(shell, spec, placed, zone_name=zone_name)


def _keep_shell(report: TraversalReport) -> None:
    """Keep an accepted build's room-gate shell for a later partial rebuild of its TER."""
    shell = getattr(report, "shell", None)
    if shell is not None and shell.key is not None and SHELLS.shell(shell.key) is None:
        SHELLS.keep_shell(shell.key, shell)


def _plan_failure_report(zone_id: str, error: Exception) -> TraversalReport:
    """A rejected attempt whose spec couldn't be planned, as a report: one
    unreachable "plan" room carrying the reason."""
    return TraversalReport(
        zone_name=zone_id, agent=AgentModel(), total_rooms=1, reachable_rooms=0,
        rooms=[RoomResult("plan", "plan", False, 0, 0, _cause(error))])


def _failure_reasons(report: TraversalReport) -> List[str]:
    """Per-room failure reasons from the report (only the unreachable rooms)."""
    out = [
        f"{r.room_id} [{r.role}]: {r.reason or 'unreachable'}"
        for r in report.rooms
        if not r.reachable
    ]
    # A shaped room's or furnished room's own verdict (steps 8 and 9).
    out += [f"{o.room_id}: {o.reason}" for o in getattr(report, "outlines", ()) if not o.ok]
    return out


def _failed_checks(report: TraversalReport, fmt: FormatReport) -> List[str]:
    """The gate/check names a rejected attempt failed, in gate order.

    ``traversability`` (some room unreachable), ``corridor_continuity`` (a
    corridor floor breaks or two corridors conflict), and the Format_Checker's
    own failed-check names (``fmt.failed_checks`` — e.g. ``diffuse_textures``).
    This is the list that rides in the JSONL ``checks`` field and the
    GenerationFailed message (Req 4.2).
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
                           checks: Sequence[str],
                           stage: str = "",
                           seeds: Optional[Mapping[str, Optional[int]]] = None,
                           ) -> AttemptFailure:
    """
    Record one rejected attempt: a structured line to stderr (via ``logging``)
    and an append-only JSONL entry to ``failure_log`` (the triage feed). The
    JSONL line carries the failed ``checks`` list (design step 5), the
    ``stage`` the report blames and the ``seeds`` the attempt used
    (world-sockets Req 9.4). Returns the AttemptFailure so the caller can
    accumulate it for GenerationFailed.
    """
    reasons = _failure_reasons(report)
    seeds = dict(seeds) if seeds is not None else {"seed": seed}
    failure = AttemptFailure(
        seed=seed,
        attempt=attempt,
        reachable_rooms=report.reachable_rooms,
        total_rooms=report.total_rooms,
        reasons=reasons,
        checks=list(checks),
        stage=stage,
        seeds=seeds,
    )

    logger.warning(
        "gate REJECT zone=%s zone_type=%s seed=%s attempt=%d "
        "reachable=%d/%d checks=%s stage=%s seeds=%s reasons=%s",
        zone_id, zone_type, seed, attempt,
        report.reachable_rooms, report.total_rooms,
        ",".join(checks) or "(none)", stage or "(none)", seeds,
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
            "stage": stage,
            "seeds": seeds,
            "reachable_rooms": report.reachable_rooms,
            "total_rooms": report.total_rooms,
            "reasons": reasons,
        }
        # The triage feed is append-only and lives at the caller's chosen path
        # (the CLI puts it inside the output dir; the Server one level up at
        # output/validation_failures.jsonl). Confine the write to the log's own
        # parent via an OutputRoot so a crafted name can't escape it, then
        # append in place (OutputRoot has no append, so open the checked path).
        p = Path(failure_log)
        log_root = OutputRoot(p.parent)
        checked = log_root.path(p.name)
        with checked.open("a", encoding="utf-8") as fh:
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
# Stage attribution (world-sockets Req 9, archive decision 5)
# ---------------------------------------------------------------------------

#: The stage a rejected attempt is blamed on: its Props (redraw ``decor_seed``),
#: its rooms (redraw ``rooms_seed``), or none named (a fresh ``seed``).
STAGE_DECOR, STAGE_ROOMS, STAGE_ZONE = "decor", "rooms", "zone"

#: Stage rerolls on one World before the retry draws a fresh ``seed``.
MAX_STAGE_REROLLS = 2

#: The ZON object names the builder gives Props (``ZoneBuilder._build_zon``).
PROP_OBJECT_PREFIX = "decor_"


def _takes_rooms_seed(factory: Callable[..., ZoneSpec]) -> bool:
    """Whether ``factory`` takes a ``rooms_seed`` keyword (a rooms reroll needs the
    planner: the layout is made in ``plan_to_spec``). One that doesn't gets a
    fresh ``seed`` for a rooms fault, as before."""
    try:
        params = inspect.signature(factory).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(p.name == "rooms_seed" or p.kind is p.VAR_KEYWORD for p in params)


def _report_without_props(eqg_path: Path, spec: ZoneSpec, agent: Optional[AgentModel],
                          report: TraversalReport) -> Optional[TraversalReport]:
    """The room gate run again with the build's Props left out (its ``decor_``
    ZON objects; the TER is the same whatever the Props, room-decor Req 6.4).
    ``report`` itself when the build has no Props. An outdoor dungeon's bowl
    keeps the verdict ``report`` gave it (the bowl judges Site Props on its own
    terms, so a fault there is never put on the rooms' Props). ``None`` for an
    open wilderness, whose one gate can't leave Props out."""
    placed = placed_models(eqg_path)
    kept = [p for p in placed if not p.name.startswith(PROP_OBJECT_PREFIX)]
    if len(kept) == len(placed):
        return report
    shell = getattr(report, "shell", None)

    def rooms_without_props() -> TraversalReport:
        # The room gate's mesh part is the same whatever the Props: judge the rest
        # against the shell the gate just used (``validate``'s own two parts).
        if shell is None:
            return validate(eqg_path, spec=spec, agent=agent, check_corridors=True, placed=kept)
        return report_with_props(shell, spec, kept, zone_name=report.zone_name)

    if is_outdoor_dungeon(spec):
        bare = rooms_without_props()
        ids = {r.id for r in spec.rooms}
        world = [r for r in report.rooms if r.room_id not in ids]
        bare.rooms = world + bare.rooms
        bare.total_rooms += len(world)
        bare.reachable_rooms += sum(r.reachable for r in world)
        return bare
    if spec.wilderness is not None:
        return None
    return rooms_without_props()


def _in_attachments(report: TraversalReport, attachments: Sequence) -> bool:
    """Whether every failure in ``report`` names a room or corridor of an
    Attachment's layout (a ``root`` or ``hillside`` Socket's rooms), and there is one."""
    names = set()
    for att in attachments or ():
        layout = getattr(att, "layout", None)
        names |= {r.id for r in getattr(layout, "rooms", ())}
        names |= {c.id for c in getattr(layout, "corridors", ())}
    failing = ([r.room_id for r in report.rooms if not r.reachable]
               + [o.room_id for o in report.outlines if not o.ok]
               + [c.corridor_id for c in report.corridors if not c.connected]
               + [cid for pair in report.conflicts for cid in pair])
    return bool(failing) and all(f in names for f in failing)


def _blame(result: BuildResult, spec: ZoneSpec, report: TraversalReport,
           fmt: FormatReport, agent: Optional[AgentModel]) -> str:
    """The stage a rejected attempt is put on, from what the gate reports
    (archive decision 5): it passes with its Props left out -> ``decor``; it
    fails without them and every failing room or corridor lies in an
    Attachment -> ``rooms``; otherwise (a format failure among them) ``zone``."""
    if not fmt.passed:
        return STAGE_ZONE
    bare = _report_without_props(result.eqg_path, spec, agent, report)
    if bare is None:
        return STAGE_ZONE
    if bare.passed and bare.corridors_passed:
        return STAGE_DECOR if bare is not report else STAGE_ZONE
    return STAGE_ROOMS if _in_attachments(bare, result.attachments) else STAGE_ZONE


def _seeds_used(spec: ZoneSpec, seed: int) -> Dict[str, Optional[int]]:
    """The three stage seeds a spec builds with, as its sidecar's ``seeds`` block."""
    return {"seed": seed,
            "rooms_seed": seed if spec.rooms_seed is None else spec.rooms_seed,
            "decor_seed": seed if spec.decor_seed is None else spec.decor_seed}


# ---------------------------------------------------------------------------
# Scratch-directory lifecycle (plain pathlib for now; OutputRoot in task 19.5)
# ---------------------------------------------------------------------------

def _scratch_dir(output_dir: Path, zone_id: str, k: int, version: int = 1) -> Path:
    """Per-attempt scratch directory: ``output_dir/.attempts/<zone_id>/a<k>/`` for v1, and
    ``.../v<version>a<k>/`` for a later version, so two rebuilds of one zone running at
    once (each with its own version number) never share a scratch folder."""
    return output_dir / ".attempts" / zone_id / (f"a{k}" if version == 1 else f"v{version}a{k}")


def _move_into(root: OutputRoot, scratch: Path, final: Path) -> None:
    """Move every file from ``scratch`` into ``final``, confined to ``root``.

    Both endpoints are checked against the Output_Directory via
    ``OutputRoot.replace`` (which ``os.replace``s on the same volume, so each
    move is atomic). ``final`` is created fresh; a stale ``final`` (e.g. a
    re-generate of the same zone id + version) is removed first — through the
    junction-safe ``OutputRoot.remove_tree`` — so the move can't collide with
    leftover files.
    """
    # Resolve both endpoints to absolute paths so ``OutputRoot.replace`` takes
    # its absolute (``_checked``) branch — a relative path would otherwise be
    # re-joined onto the root and double the ``output/`` segment.
    scratch = scratch.resolve()
    final = final.resolve()
    if final.exists():
        root.remove_tree(final)
    final.mkdir(parents=True, exist_ok=True)
    for entry in scratch.iterdir():
        root.replace(entry, final / entry.name)


def _remove_scratch(root: OutputRoot, output_dir: Path, zone_id: str,
                    scratch: Path) -> None:
    """Remove a scratch attempt dir and the now-empty ``.attempts/<zone_id>`` parent.

    Rejected and accepted attempts both call this (via the callers below) so an
    attempt never leaves a directory behind — the invariant Property 2 asserts.
    The scratch tree is removed through the junction-safe
    ``OutputRoot.remove_tree`` (never ``shutil.rmtree``, so a stray junction in
    scratch is unlinked, not followed). Removing the ``.attempts/<zone_id>``
    parent when it is empty keeps the output directory clean; the ``.attempts``
    root is likewise removed when it is empty, so a returned build leaves ONLY
    ``<zone_id>/v<version>/`` (and the failure log) behind — the Property 2
    invariant. A still-populated ``.attempts`` (another zone's in-flight
    scratch) is left untouched.
    """
    if scratch.exists():
        root.remove_tree(scratch)
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

def _plan_verticality(request: Optional[Mapping]) -> Optional[str]:
    """The verticality of the plan a request was built from (``request["plan"]``), the one
    band key the spec doesn't record; ``None`` when the request names none."""
    plan = request.get("plan") if isinstance(request, Mapping) else None
    v = plan.get("verticality") if isinstance(plan, Mapping) else None
    return v if isinstance(v, str) else None


def _judged(report: QualityReport, reason: str) -> QualityReport:
    """``report`` marked Quality_Degraded with ``reason`` when it fails its bands. A passing
    report stays not degraded, no reason, score 0 (umbrella 24.8, 25.3)."""
    if not report.passed:
        report.degraded, report.reason = True, reason
    return report


@dataclass
class _DrawBudget:
    """The quality Draws a generate has left (``QUALITY_DRAWS`` failing ones); ``done`` once
    they are spent or the timeout ran out during them: no Draws after that."""
    left: int = QUALITY_DRAWS
    done: bool = False


class _DrawsStopped(Exception):
    """A plan error during the Draws used up the attempt budget or the timeout with no
    measured spec to build: the generate fails as it would have before the Draws."""

    def __init__(self, timed_out: bool):
        super().__init__("draws stopped")
        self.timed_out = timed_out


def _quality_draw(make: Callable[[int], ZoneSpec], first: int, rng: Optional[random.Random],
                  budget: _DrawBudget, start: float, timeout_s: float,
                  bands: Optional[Mapping], verticality: Optional[str],
                  plan_failed: Callable[[int, BaseException], bool]):
    """Draw specs (``make(s)``, not built) from seed ``first`` on, fresh seeds after it, until
    one passes the bands, the budget is spent or the timeout runs out (Draw time counts
    against it). Returns ``(spec, s)``: the passing spec, else the lowest score (the earliest
    on a tie).

    A ``PLAN_ERRORS`` Draw is a rejected attempt exactly as before the Draws (lead's call,
    task 3): ``plan_failed(s, error)`` logs it (checks ``["plan"]``, stage ``zone``), moves
    the caller on to its next attempt and says whether the attempt cap and timeout still
    allow one. It is also one of the ``QUALITY_DRAWS`` (score infinity, never chosen). When
    they don't allow one: the best measured spec so far is built, or with none
    :class:`_DrawsStopped` is raised. With the Draws spent and nothing measured yet, the
    next spec drawn is built whatever it scores (a retry with no quality Draws)."""
    best = None                                   # (score, spec, seed)
    s = first
    while True:
        try:
            spec = make(s)
            report = measure(spec, bands=bands, verticality=verticality)
        except PLAN_ERRORS as e:
            budget.left -= 1
            go_on = plan_failed(s, e)
            if budget.left <= 0 or (time.monotonic() - start) >= timeout_s:
                budget.done = True
            if not go_on:
                budget.done = True
                if best is None:
                    raise _DrawsStopped((time.monotonic() - start) >= timeout_s)
                break
            if budget.done and best is not None:
                break
            s = _fresh_seed(rng)
            continue
        if report.passed:
            return spec, s
        if best is None or report.score < best[0]:
            best = (report.score, spec, s)
        budget.left -= 1
        if budget.left <= 0 or (time.monotonic() - start) >= timeout_s:
            budget.done = True
        if budget.done:
            break
        s = _fresh_seed(rng)
    logger.info("quality draws spent: building seed %s, score %.3f", best[2], best[0])
    return best[1], best[2]


def _with_decor(spec: ZoneSpec) -> ZoneSpec:
    """The spec with its Decor control resolved: one nobody chose takes the
    default (room-decor Req 10.1, ``generators.decor.rules.DEFAULT_CONTROL``).
    ``ZoneBuilder`` alone treats an unset control as ``none``."""
    if spec.decor is None:
        from generators.decor.rules import DEFAULT_CONTROL
        spec.decor = DEFAULT_CONTROL
    return spec


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
    budget_s: Optional[float] = None,
    gated_zone_types: Optional[Collection[str]] = None,
    validate_enabled: bool = True,
    agent: Optional[AgentModel] = None,
    rng: Optional[random.Random] = None,
    failure_log: Optional[str | Path] = DEFAULT_FAILURE_LOG,
    warnings: Sequence[str] = (),
    planned_zone_type: Optional[str] = None,
    mode: Optional[str] = None,
    request: Optional[Mapping] = None,
    version_meta: Optional[Mapping] = None,
    stages: Optional[SavedStages] = None,
    verticality: Optional[str] = None,
    quality_bands: Optional[Mapping] = None,
    quality_reason: Optional[str] = None,
) -> ValidatedBuild:
    """
    Build a zone and guarantee (for gated zone types) that it passes the
    traversability + corridor-continuity gate AND the Format_Checker before
    returning it — and that no rejected attempt is left on disk.

    ``spec_factory(seed)`` must return a fresh ZoneSpec for the given seed
    (name/zone_type/room-count already applied); the pipeline owns which seed to
    use on each attempt.

    Lifecycle (per attempt *k*, design "Pipeline"):

    * build into a SCRATCH dir ``output_dir/.attempts/<zone_id>/a<k>/``;
    * ``report = validate(eqg, spec, agent, check_corridors=True)`` and
      ``fmt = check_eqg(eqg, spec, sidecar_path=...)`` (the RoF2 Format_Checker);
    * PASS ⇔ ``report.passed ∧ report.corridors_passed ∧ fmt.passed``;
    * on PASS: ``os.replace`` every file into
      ``output_dir/<zone_id>/v<version>/``, merge ``format``/``warnings``/
      ``validated``/``attempts``/``seed`` (and ``planned_zone_type`` when a
      prompt-planned zone type was substituted, and ``mode`` when the caller
      names the Server/CLI path) into the Sidecar there, remove
      the scratch and its empty parent, and return;
    * on FAIL: log one JSONL line (with the failed ``checks``), ``rmtree`` the
      scratch, then the pinned / attempt-cap / timeout logic;
    * a builder EXCEPTION removes the scratch in a ``finally`` and re-raises.

    Saved inputs (partial-rebuild Req 1.4): every accepted build also gets
    ``<name>.spec.json`` (the spec it built, with its decor layers) and, when the caller
    passes ``request`` (the Server), ``<name>.request.json``: that request with the seeds
    the accepted attempt used (:func:`_write_inputs`). ``version_meta`` (a rebuild's
    ``{n, parent, changed, how}``) rides in the Sidecar as ``version``; v1 passes none.

    ``stages`` (a partial rebuild, ``generators.rebuild.rebuild_decor``): the parent's TER
    and textures, handed to every attempt's ``ZoneBuilder.build``; the gates, format check,
    map files and finalize run as for any build.

    Quality (zone-generator-quality Req 3): every build's spec is measured before it is built
    (``generators.quality.measure`` with ``quality_bands``, None: the band table, and
    ``verticality``, None: ``request["plan"]["verticality"]``, else the meter's default), and
    the report rides on ``ValidatedBuild.quality`` and in the Sidecar as ``quality``, marked
    degraded with a reason when it fails. A gated unpinned generate Draws before it builds
    (:func:`_quality_draw`): at most ``QUALITY_DRAWS`` failing specs per generate, Draw time
    inside ``timeout_s``; a rooms reroll draws its ``rooms_seed`` the same way. A Draw that
    can't be planned (``PLAN_ERRORS``) is a rejected attempt as before, logged and counted in
    ``attempts`` and ``max_attempts``, and also one of the Draws. Once the
    Draws are spent (or the timeout ran out during them), attempts build as before. A failing
    build's reason: ``quality_reason`` when given (a rebuild or an edit: measured only, never
    drawn, A4), else ``quality_outside_bands_pinned`` for a pinned seed, else
    ``quality_degraded``.

    Behaviour by scope:

    * **Ungated zone type** (zone type outside ``gated_zone_types``) or
      ``validate_enabled=False``: build ONCE through the same scratch->move
      path and return it marked ``validated=False`` (no retries, so no false-fail
      retry storm).
    * **Gated, random seed**: build -> gate -> on failure pick a NEW fresh seed
      and retry, bounded by ``max_attempts`` AND ``timeout_s`` (whichever hits
      first), except that past ``timeout_s`` an attempt still follows while the time
      run leaves room for one more of the longest attempt so far inside ``budget_s``
      (``DEFAULT_BUDGET_S`` with the default timeout, else ``timeout_s``: no change).
      At least one full attempt always completes. Returns the first
      passing build; raises :class:`GenerationFailed` when the budget is spent.
      A retry rerolls only the stage the gate blames (:func:`_blame`): Decor
      (a new ``decor_seed``) or, when ``spec_factory`` takes ``rooms_seed``,
      the rooms (a new ``rooms_seed``), keeping the World's ``seed``; at most
      ``MAX_STAGE_REROLLS`` on one World, never a stage seed the factory's spec
      already pins, and otherwise a fresh ``seed`` as before.
    * **Gated, pinned seed**: build -> gate once. On failure raise
      :class:`GenerationFailed` (``pinned=True``) rather than silently swapping
      the caller's explicit seed.
    """
    if zone_type is None:
        raise TypeError("generate_validated() requires zone_type")
    output_dir = Path(output_dir)
    # Every scratch create / move / remove below is confined to this root
    # (Req 10.1): the scratch dir, the per-build final dir and the move/cleanup
    # all resolve inside ``output_dir`` or an ``OutsideOutputError`` is raised.
    root = OutputRoot(output_dir)
    if gated_zone_types is None:
        gated_zone_types = enabled_zone_types()
    if budget_s is None:
        budget_s = DEFAULT_BUDGET_S if timeout_s is None else timeout_s
    if timeout_s is None:
        timeout_s = DEFAULT_TIMEOUT_S.get(zone_type, _FALLBACK_TIMEOUT_S)

    gated = validate_enabled and zone_type in set(gated_zone_types)
    pinned = seed is not None
    base_warnings = list(warnings)
    final_dir = output_dir / zone_id / f"v{version}"
    started = time.monotonic()
    if verticality is None:
        verticality = _plan_verticality(request)
    reason = quality_reason or (REASON_PINNED if pinned else REASON_DEGRADED)

    def judge(spec: ZoneSpec) -> QualityReport:
        return _judged(measure(spec, bands=quality_bands, verticality=verticality), reason)

    # -- Ungated / validation-disabled: single build through the scratch path.
    if not gated:
        use_seed = seed if pinned else _fresh_seed(rng)
        scratch = _scratch_dir(output_dir, zone_id, 1, version)
        try:
            spec = _with_decor(spec_factory(use_seed))
            quality = judge(spec)
            result = ZoneBuilder(spec).build(
                output_dir=scratch, write_glb=write_glb, ter_version=ter_version,
                saved=stages,
            )
            # Ungated builds still RUN the Format_Checker and RECORD it (the
            # format block in the Sidecar), even though they are not retried.
            fmt = check_eqg(result.eqg_path, spec,
                            sidecar_path=scratch / f"{spec.name.lower()}.zone.json",
                            agent=agent)
            all_warnings = base_warnings + list(result.warnings)
            map_meta = _write_map_artifacts(root, result, scratch, None, agent,
                                            all_warnings)
            _write_handoffs(root, result, scratch)
            _write_inputs(root, spec, scratch, use_seed, request, started)
            moved = _finalize_build(
                root, result, scratch, final_dir, fmt=fmt,
                warnings=all_warnings, validated=False, attempts=1,
                seed=use_seed, planned_zone_type=planned_zone_type, mode=mode,
                map_meta=map_meta, version_meta=version_meta, quality=quality,
            )
            _remove_scratch(root, output_dir, zone_id, scratch)
        except Exception:
            # Builder crash: leave nothing behind, re-raise.
            _remove_scratch(root, output_dir, zone_id, scratch)
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
            warnings=all_warnings, quality=quality,
        )

    # -- Gated: build -> gate -> retry-on-fresh-seed (random only). ----------
    start = time.monotonic()
    failures: List[AttemptFailure] = []
    attempt = 0
    # Stage rerolls (world-sockets Req 9): the stage seeds this loop drew on the
    # current World (None: the factory's own), and how many rerolls it has had.
    takes_rooms = _takes_rooms_seed(spec_factory)
    rooms_draw: Optional[int] = None
    decor_draw: Optional[int] = None
    rerolls = 0
    next_stage = STAGE_ZONE
    # Quality Draws: an unpinned generate's only (a rebuild or an edit measures, A4).
    draws = _DrawBudget(done=pinned or quality_reason is not None or stages is not None)
    longest = 0.0               # the longest attempt so far (s)

    def time_left() -> bool:
        """Whether the time allows another attempt: inside the timeout, or past it with
        room for one more of the longest attempt so far inside the whole budget."""
        spent = time.monotonic() - start
        return spent < timeout_s or spent + longest <= budget_s

    def plan_failed(draw_seeds: Dict[str, Optional[int]], error: BaseException) -> bool:
        """A Draw that can't be planned: a rejected attempt, logged as the ``PLAN_ERRORS``
        handler below logs one; the loop moves on to its next attempt. Whether the
        attempt cap and the timeout allow another (the checks after every attempt)."""
        nonlocal attempt
        failures.append(log_validation_failure(
            failure_log, zone_id=zone_id, zone_type=zone_type,
            seed=draw_seeds["seed"], attempt=attempt,
            report=_plan_failure_report(zone_id, error), checks=["plan"],
            stage=STAGE_ZONE, seeds=draw_seeds,
        ))
        go_on = attempt < max_attempts and time_left()
        attempt += 1
        return go_on

    while True:
        attempt += 1
        began = time.monotonic()
        if next_stage == STAGE_ZONE:
            use_seed = seed if pinned else _fresh_seed(rng)
            rooms_draw = decor_draw = None
            rerolls = 0
        scratch = _scratch_dir(output_dir, zone_id, attempt, version)
        stage = STAGE_ZONE
        seeds = {"seed": use_seed, "rooms_seed": rooms_draw, "decor_seed": decor_draw}
        rooms_pinned = decor_pinned = True
        try:
            if not draws.done and next_stage == STAGE_ZONE:
                spec, use_seed = _quality_draw(
                    spec_factory, use_seed, rng, draws, start, timeout_s,
                    quality_bands, verticality,
                    lambda s, e: plan_failed({"seed": s, "rooms_seed": None,
                                              "decor_seed": None}, e))
                scratch = _scratch_dir(output_dir, zone_id, attempt, version)
            elif not draws.done and next_stage == STAGE_ROOMS:
                spec, rooms_draw = _quality_draw(
                    lambda r: spec_factory(use_seed, rooms_seed=r), rooms_draw, rng, draws,
                    start, timeout_s, quality_bands, verticality,
                    lambda r, e: plan_failed({"seed": use_seed, "rooms_seed": r,
                                              "decor_seed": None}, e))
                scratch = _scratch_dir(output_dir, zone_id, attempt, version)
            else:
                spec = (spec_factory(use_seed) if rooms_draw is None
                        else spec_factory(use_seed, rooms_seed=rooms_draw))
            # A stage seed the caller chose is pinned: its stage is never rerolled.
            rooms_pinned = rooms_draw is None and spec.rooms_seed is not None
            decor_pinned = spec.decor_seed is not None
            if decor_draw is not None:
                spec.decor_seed = decor_draw
            spec = _with_decor(spec)
            seeds = _seeds_used(spec, use_seed)
            quality = judge(spec)
            result = ZoneBuilder(spec).build(
                output_dir=scratch, write_glb=write_glb, ter_version=ter_version,
                saved=stages,
            )
            # A partial rebuild judges its Props against the shell kept for its TER.
            report = (_traversal_report(result.eqg_path, spec, agent) if stages is None
                      else _traversal_report(result.eqg_path, spec, agent, reuse=True))
            fmt = check_eqg(result.eqg_path, spec,
                            sidecar_path=scratch / f"{spec.name.lower()}.zone.json",
                            agent=agent)
            passed = report.passed and report.corridors_passed and fmt.passed

            if passed:
                all_warnings = base_warnings + list(result.warnings)
                _keep_shell(report)
                map_meta = _write_map_artifacts(root, result, scratch,
                                                report.surface, agent,
                                                all_warnings, keep=True,
                                                reuse=stages is not None,
                                                ter_bytes=(stages.ter_bytes if stages
                                                           is not None else None))
                _write_handoffs(root, result, scratch)
                _write_inputs(root, spec, scratch, use_seed, request, started)
                moved = _finalize_build(
                    root, result, scratch, final_dir, fmt=fmt,
                    warnings=all_warnings, validated=True, attempts=attempt,
                    seed=use_seed, planned_zone_type=planned_zone_type,
                    mode=mode, map_meta=map_meta, version_meta=version_meta,
                    quality=quality,
                )
                _remove_scratch(root, output_dir, zone_id, scratch)
                if attempt > 1:
                    logger.info("gate PASS zone=%s zone_type=%s seed=%s on "
                                "attempt %d", zone_id, zone_type, use_seed, attempt)
                return ValidatedBuild(
                    result=moved, spec=spec, seed=use_seed, attempts=attempt,
                    validated=True, gated=True, zone_type=zone_type,
                    build_dir=final_dir, report=report, format=fmt,
                    warnings=all_warnings, quality=quality,
                )

            # Rejected — gather the failed checks, log for triage, drop scratch.
            checks = _failed_checks(report, fmt)
            stage = _blame(result, spec, report, fmt, agent)
            failures.append(log_validation_failure(
                failure_log, zone_id=zone_id, zone_type=zone_type,
                seed=use_seed, attempt=attempt, report=report, checks=checks,
                stage=stage, seeds=seeds,
            ))
            _remove_scratch(root, output_dir, zone_id, scratch)
        except PLAN_ERRORS as e:
            # The seed can't be laid out (an outdoor dungeon's hill holds too
            # few rooms, or no wall gives an Entrance): a rejected attempt,
            # retried on a fresh seed like a gate failure.
            failures.append(log_validation_failure(
                failure_log, zone_id=zone_id, zone_type=zone_type,
                seed=use_seed, attempt=attempt,
                report=_plan_failure_report(zone_id, e), checks=["plan"],
                stage=STAGE_ZONE, seeds=seeds,
            ))
            _remove_scratch(root, output_dir, zone_id, scratch)
        except _DrawsStopped as e:
            # A plan error in the Draws spent the attempt cap or the timeout, as it would
            # have without Draws (each one was logged as a rejected attempt).
            _remove_scratch(root, output_dir, zone_id, scratch)
            raise GenerationFailed(zone_id, zone_type, failures, timed_out=e.timed_out)
        except Exception:
            # Builder crash mid-attempt: leave nothing behind, re-raise.
            _remove_scratch(root, output_dir, zone_id, scratch)
            raise

        # A pinned seed is an explicit request: don't swap it, error out.
        if pinned:
            raise GenerationFailed(zone_id, zone_type, failures, pinned=True)

        # Budget check AFTER a full attempt, so at least one always finishes
        # (never return "failed" without having actually tried once).
        if attempt >= max_attempts:
            raise GenerationFailed(zone_id, zone_type, failures)
        longest = max(longest, time.monotonic() - began)
        if not time_left():
            raise GenerationFailed(zone_id, zone_type, failures, timed_out=True)

        # Retry the stage blamed on the same World, at most MAX_STAGE_REROLLS
        # times and never a pinned stage; else a fresh seed for everything.
        next_stage = STAGE_ZONE
        if rerolls < MAX_STAGE_REROLLS:
            if stage == STAGE_DECOR and not decor_pinned:
                decor_draw, next_stage = _fresh_seed(rng), STAGE_DECOR
            elif stage == STAGE_ROOMS and takes_rooms and not rooms_pinned:
                # Decor is a later stage: it follows the new rooms.
                rooms_draw, decor_draw, next_stage = _fresh_seed(rng), None, STAGE_ROOMS
        if next_stage != STAGE_ZONE:
            rerolls += 1


# ---------------------------------------------------------------------------
# Map post-pass (M2): outline SVG + EQ map files for the accepted build only
# ---------------------------------------------------------------------------

_CAUSE_JUNK = re.compile(r"[^A-Za-z0-9_ .:-]")


def _cause(e: BaseException) -> str:
    """A warning-safe cause: the exception type plus the first line of its
    message, ``[A-Za-z0-9_ .:-]`` only, at most 120 characters, so a warning
    never carries a path outside the Output_Directory or a key."""
    msg = str(e).splitlines()[0] if str(e) else ""
    text = f"{type(e).__name__}: {msg}" if msg else type(e).__name__
    return _CAUSE_JUNK.sub("", text)[:120]


def _write_map_artifacts(root: OutputRoot, result: BuildResult, scratch: Path,
                         surface, agent: Optional[AgentModel],
                         warnings: List[str], *, keep: bool = False,
                         reuse: bool = False, ter_bytes: Optional[bytes] = None) -> dict:
    """Write ``<name>.map.svg`` and ``maps/<name>*.txt`` into ``scratch``.

    Runs after the gates pass, before the move out of scratch (design
    "Pipeline post-pass"). Never fails the build: an extractor failure or an
    empty floor gives the schematic-only SVG and no ``maps/``
    (``outline_unavailable:<cause>``); a writer failure keeps the outline SVG
    and removes ``maps/`` (``eqmap_unavailable:<cause>``). Warnings are
    appended to ``warnings``; returns the Sidecar's ``map_files``/``outline``.

    The outline traced from the TER is kept per TER (``generators.rebuild.SHELLS``) with
    ``keep``, and with ``reuse`` (a partial rebuild) a kept one is used instead of tracing
    it again (Req 4.4); the map files are drawn again with this build's Props. ``ter_bytes``
    are the build's TER bytes when the caller has them (a partial rebuild's are the
    parent's, ``ZoneBuilder.build`` checks they are), so the ``.eqg`` isn't read for them.
    """
    spec = result.spec
    name = spec.name.lower()
    scratch = scratch.resolve()
    try:
        if ter_bytes is None:
            data, zone_name = ter_bytes_from_eqg(result.eqg_path)
        else:
            data, zone_name = ter_bytes, Path(result.eqg_path).stem.lower()
        key = SHELLS.key(data, spec, agent) if keep or reuse else None
        traced = SHELLS.outline(key) if reuse else None
        if traced is None:
            ter = TerFile.from_bytes(data, name=zone_name)
            traced = extract_outline(ter, spec.safe_point, agent, surface=surface)
            if key is not None:
                SHELLS.keep_outline(key, traced)
        outline = with_solids(traced, spec)
    except Exception as e:                       # EmptyFloorRegion or a bug
        logger.warning("outline extraction failed for %s", name, exc_info=True)
        outline = None
        warnings.append(f"outline_unavailable:{_cause(e)}")
    # Sites (wilderness / outdoor dungeon): what this build wrote, Footprints
    # from the .eqg and labels from the sidecar, never a second placement.
    sites = None
    sidecar = None
    if result.sidecar_path is not None and (spec.wilderness is not None or spec.decor not in (None, "none")):
        try:
            sidecar = json.loads(Path(result.sidecar_path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.warning("sidecar unreadable for %s", name, exc_info=True)
            warnings.append(f"{'sites' if spec.wilderness is not None else 'props'}_unmapped:{_cause(e)}")
    if spec.wilderness is not None and sidecar is not None:
        try:
            sites = site_marks(result.eqg_path, sidecar)
        except Exception as e:
            logger.warning("site marks failed for %s", name, exc_info=True)
            warnings.append(f"sites_unmapped:{_cause(e)}")
    # Props (room-decor Req 10.4): the built ones, from the .eqg and the sidecar,
    # over the traced outline only (a failed trace stays the plain schematic).
    props = None
    if outline is not None and sidecar is not None and sidecar.get("decor"):
        try:
            props = prop_marks(result.eqg_path, sidecar)
        except Exception as e:
            logger.warning("prop marks failed for %s", name, exc_info=True)
            warnings.append(f"props_unmapped:{_cause(e)}")
    svg_path = root.write_text(str(scratch / f"{name}.map.svg"),
                               render_map_svg(spec, outline=outline, sites=sites, props=props))
    result.map_path = svg_path
    map_files = [svg_path.name]
    if outline is None:
        return {"map_files": map_files, "outline": None}

    block = outline_summary(outline)
    maps_dir = scratch / "maps"
    try:
        mf = build_map_file(outline, spec, name, sites=sites, props=props)
        written = write_map_files(mf, maps_dir, root)
        files = {l.index: f"maps/{mf.filename(l.index)}" for l in mf.layers}
        map_files += [f"maps/{p.name}" for p in written]
    except Exception as e:
        logger.warning("EQ map writing failed for %s", name, exc_info=True)
        root.remove_tree(maps_dir)
        files = {}
        warnings.append(f"eqmap_unavailable:{_cause(e)}")
    for band in block["bands"]:
        band["file"] = files.get(band["index"])
    return {"map_files": map_files, "outline": block}


def _write_handoffs(root: OutputRoot, result: BuildResult, scratch: Path) -> None:
    """Write the build's hand-offs into ``scratch`` (world-sockets Req 5.1, decision 6):
    ``<name>.world.json``, ``<name>.attach.json``, ``<name>.rooms.json``. For the accepted
    build only, as the maps are; not page downloads, and never read back here."""
    if result.world is None:
        return
    scratch = scratch.resolve()
    for fname, text in result.handoffs().items():
        root.write_bytes(str(scratch / fname), text.encode("utf-8"))


def _write_inputs(root: OutputRoot, spec: ZoneSpec, scratch: Path, seed: int,
                  request: Optional[Mapping], started: float) -> None:
    """Write what a rebuild needs into ``scratch`` (partial-rebuild Req 1.4), for the
    accepted build only, as the hand-offs are:

    * ``<name>.spec.json``: ``ZoneSpec.to_dict`` (what ``ZoneSpec.save`` writes) plus
      ``decor_layers``, the request's extra decor layers, which ride beside the spec
      (``builder.with_decor_layers``), not in it.
    * ``<name>.request.json`` when ``request`` is given: the request with the seeds the
      accepted attempt built with, ``seed`` the zone's and ``rooms_seed`` / ``decor_seed``
      the spec's stage seeds (``None``: the zone's seed stands in; a stage the pipeline
      rerolled names the seed it drew), so sending it again builds the same zone. Plus
      ``seeds`` (all three resolved, as the Sidecar's), ``took_ms`` (the pipeline's wall
      time to here, every attempt included) and ``created`` (UTC, ISO 8601).
    """
    scratch = scratch.resolve()
    name = spec.name.lower()
    spec_doc = {**spec.to_dict(), "decor_layers": list(getattr(spec, "decor_layers", ()) or ())}
    root.write_text(str(scratch / f"{name}.spec.json"), json.dumps(spec_doc, indent=2))
    if request is None:
        return
    doc = {**dict(request), "seed": seed, "rooms_seed": spec.rooms_seed,
           "decor_seed": spec.decor_seed, "seeds": _seeds_used(spec, seed),
           "took_ms": int(round((time.monotonic() - started) * 1000)),
           "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    root.write_text(str(scratch / f"{name}.request.json"), json.dumps(doc, indent=2))


def _finalize_build(root: OutputRoot, result: BuildResult, scratch: Path,
                    final_dir: Path, *,
                    fmt: FormatReport, warnings: Sequence[str], validated: bool,
                    attempts: int, seed: int,
                    planned_zone_type: Optional[str] = None,
                    mode: Optional[str] = None,
                    map_meta: Optional[dict] = None,
                    version_meta: Optional[Mapping] = None,
                    quality: Optional[QualityReport] = None) -> BuildResult:
    """Move a passing/ungated build out of scratch into ``final_dir``.

    Moves every file from ``scratch`` into ``final_dir`` through
    ``OutputRoot.replace`` (atomic on the same volume, both endpoints confined),
    merges the pipeline fields (``format``/``warnings``/``validated``/
    ``attempts``/``seed``, plus ``planned_zone_type`` when a substitution
    occurred) into the Sidecar there, and rewrites the BuildResult paths to
    point at their new home. The scratch directory is removed by the caller (so
    the one ``finally`` cleanup covers both the success and failure exits).
    """
    _move_into(root, scratch, final_dir)

    # Resolve to absolute so the derived Sidecar / relocated paths are absolute
    # and ``OutputRoot.write_text`` takes its checked (non-rejoining) branch — a
    # relative ``final_dir`` would otherwise be re-joined onto the root and
    # double the output segment.
    final_dir = final_dir.resolve()

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
        # ``mode`` records which Server/CLI path produced the build ("prompt" |
        # "controls"), recorded in the Sidecar when the caller passes it (the
        # CLI and ungated builds may omit it).
        if mode is not None:
            data["mode"] = mode
        # ``map_files`` (relative to the build dir) and the ``outline`` block
        # from the map post-pass (M2 Req 8.4).
        if map_meta is not None:
            data.update(map_meta)
        # A rebuild's ``version`` block (partial-rebuild Req 1.2); a v1 build has none.
        if version_meta is not None:
            data["version"] = dict(version_meta)
        # The Quality_Block (zone-generator-quality Req 3.3, umbrella 25.4).
        if quality is not None:
            data["quality"] = quality_summary(quality)
        # Rewrite in place, confined to the Output_Directory.
        root.write_text(str(sidecar), json.dumps(data, indent=2))

    return result
