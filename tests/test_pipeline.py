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
    DEFAULT_GATED_THEMES,
)

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
    spec = LayoutGenerator(theme="dungeon", seed=GOOD_SEED).generate(
        "pipe", room_count=rooms)
    spec.rooms.append(RoomSpec(
        id="isolated", center_x=100_000.0, center_y=100_000.0, floor_z=0.0,
        width=200, depth=200, height=100))
    return spec


def _good_factory(rooms=5):
    def f(seed):
        return LayoutGenerator(theme="dungeon", seed=GOOD_SEED).generate(
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
        return LayoutGenerator(theme="dungeon", seed=GOOD_SEED).generate(
            "pipe", room_count=5)
    return f


def _run(factory, tmp_path, **kw):
    kw.setdefault("theme", "dungeon")
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
        assert "dungeon" in DEFAULT_GATED_THEMES
        assert "outdoor" not in DEFAULT_GATED_THEMES

    def test_ungated_theme_passes_through_without_retry(self, tmp_path):
        # Force "dungeon" to be ungated: even a would-fail zone is returned as-is
        # (validated=False) with NO retries and NO failure-log storm.
        vb = _run(_bad_factory(), tmp_path, gated_themes=frozenset(),
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
        for key in ("ts", "zone_id", "theme", "seed", "attempt",
                    "reachable_rooms", "total_rooms", "reasons"):
            assert key in rec, f"missing {key} in failure log line"
        assert rec["theme"] == "dungeon"
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
            name="cli", theme="dungeon", rooms=8, seed=PINNED_SEED,
            output=str(tmp_path), ter_version=2,
            no_validate=False,
        )
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    def test_no_validate_builds_broken_seed(self, tmp_path):
        import main
        main.cmd_generate(self._args(tmp_path, no_validate=True))
        assert (tmp_path / "cli.eqg").exists()
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
    whose theme is dungeon (M0 Req 6.9): the cave pipeline is gone, so cave
    prompts plan and build as gated dungeons."""
    from ai.rule_planner import RulePlanner
    from ai.expand import plan_to_spec

    plan = RulePlanner().plan("a dark underground cavern with many tunnels")
    assert plan.theme == "dungeon"

    def factory(s):
        return plan_to_spec(plan, seed=s)

    vb = generate_validated(
        factory, theme=plan.theme, zone_id="cavedungeon",
        output_dir=str(tmp_path), write_glb=False,
        failure_log=tmp_path / "fail.jsonl",
    )
    assert vb.validated
    assert vb.spec.theme == "dungeon"
