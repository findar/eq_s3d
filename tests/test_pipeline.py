"""
tests/test_pipeline.py
----------------------
Tests for the validated generation pipeline (``generators.pipeline``) — the
layer that bakes the traversability validator into the hot path so a broken
dungeon never reaches a client.

Covers the acceptance checklist for tasks/validate-in-pipeline.md:
  * returns a passing build when one exists (first try + after fresh-seed retry)
  * raises GenerationFailed on attempt-cap exhaustion
  * respects the wall-clock timeout (returns, doesn't hang)
  * writes a structured JSONL failure line per rejected attempt
  * honours the pinned-seed rule (error, never a silent seed swap)
  * ungated themes pass through unvalidated with NO retry storm
  * the CLI --no-validate escape hatch bypasses the gate

Determinism: we drive the pipeline with factories that deterministically PASS
(seed 1, flat 5-room dungeon) or FAIL. Since corridor-connection landed, no
well-formed seed is reliably broken any more, so a failing zone is produced
by CONSTRUCTION — a good zone plus one isolated room with no corridor, which is
unreachable regardless of corridor routing. Builds use write_glb=False to stay
fast and avoid the trimesh dependency.
"""

import json
import random
from pathlib import Path

import pytest

from generators.layout import LayoutGenerator
from generators.zone_spec import RoomSpec
from generators.pipeline import (
    generate_validated,
    GenerationFailed,
    ValidatedBuild,
)
from generators.zone_types import ENABLED_ZONE_TYPES

GOOD_SEED = 1
# A pinned-seed value for the pinned-seed tests. Its brokenness is no longer
# relevant (the factory decides the outcome), it's just a stable seed number.
PINNED_SEED = 1955208177


# ---------------------------------------------------------------------------
# Factories (ignore the pipeline's fresh seed on purpose, to force outcomes)
# ---------------------------------------------------------------------------

def _broken_spec(rooms=5):
    """
    A deterministically-unreachable zone: a good base zone plus one ISOLATED
    room that no corridor connects to. The validator must always reject it,
    independent of corridor routing — the robust stand-in for the old
    reliably-broken seed now that corridor-connection makes seeds connect.
    """
    spec = LayoutGenerator(zone_type="dungeon", seed=GOOD_SEED).generate(
        "pipe", room_count=rooms)
    spec.rooms.append(RoomSpec(
        id="isolated", center_x=100_000.0, center_y=100_000.0, floor_z=0.0,
        width=200, depth=200, height=100))
    return spec


def _good_factory(rooms=5):
    def f(seed):
        return LayoutGenerator(zone_type="dungeon", seed=GOOD_SEED).generate(
            "pipe", room_count=rooms)
    return f


def _bad_factory(rooms=8):
    def f(seed):
        return _broken_spec()
    return f


def _flaky_factory(fail_times):
    """Fail the first ``fail_times`` attempts, then produce a passing zone."""
    calls = {"n": 0}

    def f(seed):
        calls["n"] += 1
        if calls["n"] <= fail_times:
            return _broken_spec()
        return LayoutGenerator(zone_type="dungeon", seed=GOOD_SEED).generate(
            "pipe", room_count=5)
    return f


def _run(factory, tmp_path, **kw):
    kw.setdefault("zone_type", "dungeon")
    kw.setdefault("zone_id", "pipe")
    kw.setdefault("output_dir", str(tmp_path))
    kw.setdefault("write_glb", False)
    kw.setdefault("failure_log", tmp_path / "fail.jsonl")
    return generate_validated(factory, **kw)


def _log_lines(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# Passing paths
# ---------------------------------------------------------------------------

class TestPasses:
    def test_returns_passing_build_first_try(self, tmp_path):
        vb = _run(_good_factory(), tmp_path, max_attempts=3)
        assert isinstance(vb, ValidatedBuild)
        assert vb.validated and vb.gated
        assert vb.attempts == 1
        assert vb.report is not None and vb.report.passed
        assert Path(vb.result.eqg_path).exists()
        # Nothing rejected -> no failure log lines.
        assert _log_lines(tmp_path / "fail.jsonl") == []

    def test_retries_on_fresh_seed_then_succeeds(self, tmp_path):
        vb = _run(_flaky_factory(fail_times=2), tmp_path,
                  max_attempts=8, rng=random.Random(0))
        assert vb.validated
        assert vb.attempts == 3                 # 2 rejected + 1 pass
        # Each rejected attempt logged exactly once.
        lines = _log_lines(tmp_path / "fail.jsonl")
        assert len(lines) == 2
        assert [ln["attempt"] for ln in lines] == [1, 2]


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------

class TestExhaustion:
    def test_attempt_cap_raises(self, tmp_path):
        with pytest.raises(GenerationFailed) as ei:
            _run(_bad_factory(), tmp_path, max_attempts=3, rng=random.Random(1))
        err = ei.value
        assert err.attempts == 3
        assert not err.pinned and not err.timed_out
        assert len(err.failures) == 3
        # One JSONL line per rejected attempt.
        assert len(_log_lines(tmp_path / "fail.jsonl")) == 3

    def test_timeout_returns_promptly(self, tmp_path):
        # timeout_s=0 -> after the first (full) attempt the wall-clock budget is
        # already spent, so it stops without burning all 100 attempts.
        with pytest.raises(GenerationFailed) as ei:
            _run(_bad_factory(), tmp_path, max_attempts=100, timeout_s=0.0,
                 rng=random.Random(2))
        err = ei.value
        assert err.timed_out
        assert err.attempts == 1            # at least one full attempt ran


class TestPinnedSeed:
    def test_pinned_failure_errors_without_retry(self, tmp_path):
        with pytest.raises(GenerationFailed) as ei:
            _run(_bad_factory(), tmp_path, seed=PINNED_SEED, max_attempts=8)
        err = ei.value
        assert err.pinned
        assert err.attempts == 1            # pinned: built once, never swapped
        assert len(_log_lines(tmp_path / "fail.jsonl")) == 1

    def test_pinned_success_returns(self, tmp_path):
        vb = _run(_good_factory(), tmp_path, seed=GOOD_SEED, max_attempts=8)
        assert vb.validated and vb.attempts == 1
        assert vb.seed == GOOD_SEED


# ---------------------------------------------------------------------------
# Gating scope
# ---------------------------------------------------------------------------

class TestGating:
    def test_dungeon_is_gated_by_default(self):
        # task 15.4 removed the separate DEFAULT_GATED_ZONE_TYPES: the gated set
        # now defaults to the one Enabled set (Req 3.1). Dungeon is enabled and
        # therefore gated; wilderness is disabled in M1 and so ungated.
        assert "dungeon" in ENABLED_ZONE_TYPES
        assert "wilderness" not in ENABLED_ZONE_TYPES

    def test_ungated_zone_type_passes_through_without_retry(self, tmp_path):
        # Force "dungeon" to be ungated: even a would-fail zone is returned as-is
        # (validated=False) with NO retries and NO failure-log storm.
        vb = _run(_bad_factory(), tmp_path, gated_zone_types=frozenset(),
                  max_attempts=8)
        assert not vb.validated and not vb.gated
        assert vb.attempts == 1
        assert _log_lines(tmp_path / "fail.jsonl") == []

    def test_validate_disabled_bypasses_gate(self, tmp_path):
        # The --no-validate code path: a known-bad gated zone builds anyway.
        vb = _run(_bad_factory(), tmp_path, validate_enabled=False,
                  max_attempts=8)
        assert not vb.validated
        assert vb.attempts == 1
        assert Path(vb.result.eqg_path).exists()


# ---------------------------------------------------------------------------
# Structured failure log shape
# ---------------------------------------------------------------------------

class TestFailureLog:
    def test_line_has_triage_fields(self, tmp_path):
        with pytest.raises(GenerationFailed):
            _run(_bad_factory(), tmp_path, seed=PINNED_SEED, max_attempts=1)
        lines = _log_lines(tmp_path / "fail.jsonl")
        assert len(lines) == 1
        rec = lines[0]
        for key in ("ts", "zone_id", "zone_type", "seed", "attempt",
                    "reachable_rooms", "total_rooms", "reasons"):
            assert key in rec, f"missing {key} in failure log line"
        assert rec["zone_type"] == "dungeon"
        assert rec["reachable_rooms"] < rec["total_rooms"]
        # Per-room reasons present — the data corridor-connection triages on.
        assert rec["reasons"] and all(isinstance(r, str) for r in rec["reasons"])


# ---------------------------------------------------------------------------
# CLI integration (shared helper -> same guarantee as the server)
# ---------------------------------------------------------------------------

class TestCliEscapeHatch:
    def _args(self, tmp_path, **over):
        import argparse
        ns = argparse.Namespace(
            name="cli", zone_type="dungeon", rooms=8, seed=PINNED_SEED,
            output=str(tmp_path), ter_version=2,
            no_validate=False,
        )
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    def test_no_validate_builds_broken_seed(self, tmp_path):
        import main
        main.cmd_generate(self._args(tmp_path, no_validate=True))
        # task 15.4 moves accepted/ungated builds into <zone_id>/v<version>/;
        # the .eqg lives there now. The spec is still saved flat by main.py.
        assert (tmp_path / "cli" / "v1" / "cli.eqg").exists()
        assert (tmp_path / "cli.json").exists()

    def test_gate_blocks_pinned_bad_seed(self, tmp_path, monkeypatch):
        # Force the CLI to build a broken zone (an isolated, corridor-less room)
        # so the pinned-seed gate must error out. No seed is reliably broken any
        # more, so we inject the breakage rather than rely on one.
        import main
        from generators.layout import LayoutGenerator as _RealLG

        class _BrokenLG(_RealLG):
            def generate(self, *a, **k):
                spec = super().generate(*a, **k)
                spec.rooms.append(RoomSpec(
                    id="isolated", center_x=100_000.0, center_y=100_000.0,
                    floor_z=0.0, width=200, depth=200, height=100))
                return spec

        monkeypatch.setattr(main, "LayoutGenerator", _BrokenLG)
        with pytest.raises(SystemExit) as ei:
            main.cmd_generate(self._args(tmp_path, no_validate=False))
        assert ei.value.code == 1


# ---------------------------------------------------------------------------
# CLI argument handling (M0 6.8, 6.9)
# ---------------------------------------------------------------------------

class TestCliArgs:
    def test_legacy_theme_outdoor_equivalent_to_zone_type_wilderness(
            self, tmp_path, monkeypatch):
        """CLI legacy alias maps forward: ``--theme outdoor`` resolves to the
        SAME zone type as ``--zone-type wilderness`` (Req 11.3).

        ``--theme`` is the kept legacy LOAD boundary on the CLI; it shares the
        ``zone_type`` argparse dest and its value is legacy-mapped. This asserts
        the two invocations drive ``cmd_generate`` to the identical resolved
        zone type (``wilderness``) — the build itself is stubbed so the check is
        fast and isolated to the argument plumbing.
        """
        import main
        from generators.zone_types import canonical_zone_type, DEFAULT_ZONE_TYPE

        seen = {}

        def _capture(args):
            raw = getattr(args, "zone_type", None)
            if raw is None:
                raw = getattr(args, "theme", None)
            seen["zt"] = canonical_zone_type(raw) or DEFAULT_ZONE_TYPE

        monkeypatch.setattr(main, "cmd_generate", _capture)

        out = str(tmp_path / "o")
        main.main(["generate", "legacy", "--theme", "outdoor", "--output", out])
        legacy_zt = seen["zt"]
        main.main(["generate", "modern", "--zone-type", "wilderness",
                   "--output", out])
        modern_zt = seen["zt"]

        assert legacy_zt == "wilderness"
        assert legacy_zt == modern_zt, (
            f"--theme outdoor resolved to {legacy_zt!r} but "
            f"--zone-type wilderness resolved to {modern_zt!r}"
        )

    def test_cave_theme_rejected_by_argparse(self, tmp_path):
        # "cave" was removed from the --theme choices (M0 6.8): argparse exits 2
        # in parse_args, before any build, so no output directory is created.
        # Driven in-process via the main(argv) entry point (task 6.1).
        import main
        out = str(tmp_path / "cli_out")
        with pytest.raises(SystemExit) as ei:
            main.main(["generate", "x", "--theme", "cave", "--output", out])
        assert ei.value.code == 2
        assert not Path(out).exists()

    # -- Removed preview paths (M0 6.2) -----------------------------------
    # The legacy viewer and its CLI entry points were deleted in task 6.1:
    # the "preview" subcommand and the "--preview" option are both gone, so
    # argparse rejects them in parse_args (exit 2) before any build runs. The
    # no_network fixture proves no preview server could have started: it
    # records every non-loopback connect/bind, so attempts == [] means no
    # foreign listener opened. 'out' must stay absent because argparse exits
    # before cmd_generate creates the output directory.

    def test_preview_subcommand_rejected(self, capsys, no_network):
        # `preview` is no longer a subcommand: argparse reports it as an
        # invalid choice and exits 2, with no network activity.
        import main
        with pytest.raises(SystemExit) as ei:
            main.main(["preview", "x"])
        assert ei.value.code == 2
        err = capsys.readouterr().err
        assert "invalid choice" in err
        assert "preview" in err
        assert no_network == []          # no non-loopback bind / listener

    def test_preview_option_rejected(self, capsys, tmp_path, no_network):
        # `--preview` is no longer an option on `generate`: argparse reports it
        # as unrecognized and exits 2, before any output dir is created.
        import main
        out = str(tmp_path / "prev_out")
        with pytest.raises(SystemExit) as ei:
            main.main(["generate", "x", "--preview", "--output", out])
        assert ei.value.code == 2
        err = capsys.readouterr().err
        assert "unrecognized arguments" in err
        assert "--preview" in err
        assert no_network == []          # no non-loopback bind / listener
        assert not Path(out).exists()    # argparse exits before any build

    def test_help_does_not_mention_preview(self, capsys):
        # --help exits 0 and writes usage to stdout; neither the top-level nor
        # the `generate` help should mention the removed preview path.
        import main
        with pytest.raises(SystemExit) as ei:
            main.main(["--help"])
        assert ei.value.code == 0
        top = capsys.readouterr().out
        assert "preview" not in top.lower()

        with pytest.raises(SystemExit) as ei:
            main.main(["generate", "--help"])
        assert ei.value.code == 0
        gen = capsys.readouterr().out
        assert "preview" not in gen.lower()


# ---------------------------------------------------------------------------
# Cave words plan a validated dungeon end-to-end (M0 6.9)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_cave_prompt_builds_validated_dungeon(tmp_path):
    """An unpinned pipeline run on a cave-word prompt returns a validated build
    whose zone_type is dungeon (M0 Req 6.9): the cave pipeline is gone, so cave
    prompts plan and build as gated dungeons."""
    from ai.rule_planner import RulePlanner
    from ai.expand import plan_to_spec

    plan = RulePlanner().plan("a dark underground cavern with many tunnels")
    assert plan.zone_type == "dungeon"

    def factory(s):
        return plan_to_spec(plan, seed=s)

    vb = generate_validated(
        factory, zone_type=plan.zone_type, zone_id="cavedungeon",
        output_dir=str(tmp_path), write_glb=False,
        failure_log=tmp_path / "fail.jsonl",
    )
    assert vb.validated
    assert vb.spec.zone_type == "dungeon"


# ---------------------------------------------------------------------------
# Backend fallback (task 12.3, Req 4.3 / 7.1)
# ---------------------------------------------------------------------------

class TestBackendFallback:
    def test_wilderness_falls_back_to_box_when_terrain_unavailable(
            self, tmp_path, monkeypatch):
        """A wilderness build succeeds on the box backend when terrain can't run.

        Simulates the numpy-less machine (design finding: TerrainBackend.build
        returns None) by monkeypatching ``TerrainBackend.build`` to return None.
        The build must still SUCCEED, report ``backend == "box"``, and surface
        the ``backend_fallback`` warning rather than crashing. Req 4.3, 7.1.
        """
        from generators.backends import TerrainBackend
        from generators.builder import ZoneBuilder

        # Terrain unavailable -> backend_for("wilderness").build(...) returns None.
        monkeypatch.setattr(TerrainBackend, "build",
                            lambda self, spec, ter_name, ter_version: None)

        spec = LayoutGenerator(zone_type="wilderness", seed=GOOD_SEED).generate(
            "wild", room_count=5)
        assert spec.zone_type == "wilderness"   # really the terrain backend path

        result = ZoneBuilder(spec).build(output_dir=str(tmp_path),
                                         write_glb=False)

        # Build succeeded via the box fallback.
        assert Path(result.eqg_path).exists()
        assert result.backend == "box"
        assert ("backend_fallback: terrain unavailable, built with box"
                in result.warnings)


# ---------------------------------------------------------------------------
# Pipeline lifecycle example tests (task 15.9, Req 4.2 / 4.3)
# ---------------------------------------------------------------------------
#
# Deterministic wiring/behaviour checks for the wave-4 generate_validated
# lifecycle (task 15.4): a builder crash leaves no scratch behind, an ungated
# build carries its format block and validated=False, and a backend_fallback
# warning reaches both ValidatedBuild.warnings and the written Sidecar. These
# are example tests, not property tests — they pin specific wiring, not an
# input-varying invariant.

class TestPipelineLifecycle:
    def _sidecar(self, vb):
        """Read the merged Sidecar JSON the pipeline wrote for ``vb``."""
        path = Path(vb.result.sidecar_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def test_builder_exception_removes_scratch_and_propagates(
            self, tmp_path, monkeypatch):
        """A builder exception mid-build propagates AND leaves no scratch.

        The per-attempt build is wrapped so a crash calls ``_remove_scratch``
        and re-raises (generators/pipeline.py). We monkeypatch
        ``ZoneBuilder.build`` to raise, assert the exception propagates, and
        assert nothing is left under ``output_dir`` — in particular no
        ``.attempts/`` scratch tree (Req 4.2's "a rejected/crashed attempt
        leaves nothing behind")."""
        from generators.builder import ZoneBuilder

        class _Boom(RuntimeError):
            pass

        def _raise(self, *a, **k):
            raise _Boom("builder crashed mid-build")

        monkeypatch.setattr(ZoneBuilder, "build", _raise)

        with pytest.raises(_Boom):
            _run(_good_factory(), tmp_path, max_attempts=3)

        # The crash re-raised, and the scratch tree was cleaned up: no
        # .attempts dir, and no per-build dir was created either.
        assert not (tmp_path / ".attempts").exists()
        assert not (tmp_path / "pipe").exists()

    def test_ungated_build_carries_format_block_and_validated_false(
            self, tmp_path):
        """An ungated build is returned ``validated=False`` but still records a
        ``format`` block in both the result and the Sidecar.

        Forcing an empty gated set makes even a dungeon ungated; the pipeline
        runs it once through the same scratch->move path, marks it
        ``validated=False``, and still writes the (stub) ``format`` block to the
        Sidecar (Req 4.2)."""
        vb = _run(_good_factory(), tmp_path, gated_zone_types=frozenset(),
                  max_attempts=8)

        assert vb.validated is False
        assert vb.gated is False
        # The format block is present on the build and is the passing stub shape.
        assert vb.format is not None
        fmt = vb.format.to_dict()
        assert set(fmt) == {"passed", "checks"}
        assert fmt["passed"] is True

        # ...and it reaches the written Sidecar, alongside validated=False.
        data = self._sidecar(vb)
        assert data["validated"] is False
        assert data["format"] == fmt

    def test_backend_fallback_reaches_warnings_and_sidecar(
            self, tmp_path, monkeypatch):
        """A builder ``backend_fallback`` warning flows to ``vb.warnings`` and
        the Sidecar.

        A wilderness spec routes through ``TerrainBackend``; monkeypatching its
        ``build`` to return ``None`` (the numpy-less machine) makes the builder
        fall back to box and emit a ``backend_fallback`` warning. Wilderness is
        not in the Enabled set, so the build is ungated and runs once; the
        pipeline merges ``result.warnings`` into both ``vb.warnings`` and the
        written Sidecar (Req 4.3)."""
        from generators.backends import TerrainBackend

        monkeypatch.setattr(TerrainBackend, "build",
                            lambda self, spec, ter_name, ter_version: None)

        def factory(seed):
            return LayoutGenerator(zone_type="wilderness", seed=GOOD_SEED).generate(
                "pipe", room_count=5)

        vb = _run(factory, tmp_path, zone_type="wilderness", max_attempts=8)

        # Ungated (wilderness is disabled in M1), built once via the box fallback.
        assert vb.validated is False
        assert vb.result.backend == "box"

        fallback = "backend_fallback: terrain unavailable, built with box"
        assert fallback in vb.warnings

        data = self._sidecar(vb)
        assert fallback in data["warnings"]
