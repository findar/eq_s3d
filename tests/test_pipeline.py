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

Determinism: we drive the pipeline with factories pinned to seeds the
traversability suite already proves reliably PASS (seed 1, flat 5-room dungeon)
or reliably FAIL (seed 1955208177, 8-room elevation dungeon). Builds use
write_glb=False to stay fast and avoid the trimesh dependency.
"""

import json
import random
from pathlib import Path

import pytest

from generators.layout import LayoutGenerator
from generators.pipeline import (
    generate_validated,
    GenerationFailed,
    ValidatedBuild,
    DEFAULT_GATED_THEMES,
)

# Seeds the traversability regression suite asserts on (not xfail):
#   test_traversability.TestKnownGoodDungeons  -> seed 1, rooms=5 fully reachable
#   test_traversability.test_validator_flags_the_breakage -> seed 1955208177,
#   rooms=8 is reliably broken (hard assertion there).
GOOD_SEED = 1
BAD_SEED = 1955208177


# ---------------------------------------------------------------------------
# Factories (ignore the pipeline's fresh seed on purpose, to force outcomes)
# ---------------------------------------------------------------------------

def _good_factory(rooms=5):
    def f(seed):
        return LayoutGenerator(theme="dungeon", seed=GOOD_SEED).generate(
            "pipe", room_count=rooms)
    return f


def _bad_factory(rooms=8):
    def f(seed):
        return LayoutGenerator(theme="dungeon", seed=BAD_SEED).generate(
            "pipe", room_count=rooms)
    return f


def _flaky_factory(fail_times):
    """Fail the first ``fail_times`` attempts, then produce a passing zone."""
    calls = {"n": 0}

    def f(seed):
        calls["n"] += 1
        if calls["n"] <= fail_times:
            return LayoutGenerator(theme="dungeon", seed=BAD_SEED).generate(
                "pipe", room_count=8)
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
            _run(_bad_factory(), tmp_path, seed=BAD_SEED, max_attempts=8)
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
        assert "cave" not in DEFAULT_GATED_THEMES

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
            _run(_bad_factory(), tmp_path, seed=BAD_SEED, max_attempts=1)
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
            name="cli", theme="dungeon", rooms=8, seed=BAD_SEED,
            output=str(tmp_path), ter_version=2, preview=False,
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

    def test_gate_blocks_pinned_bad_seed(self, tmp_path):
        import main
        with pytest.raises(SystemExit) as ei:
            main.cmd_generate(self._args(tmp_path, no_validate=False))
        assert ei.value.code == 1
