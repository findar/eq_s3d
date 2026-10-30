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
        # now defaults to the one Enabled set (Req 3.1). Dungeon and wilderness
        # are enabled and therefore gated.
        assert {"dungeon", "wilderness"} <= ENABLED_ZONE_TYPES

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
            name="cli", zone_type="dungeon", rooms=8, size="medium",
            verticality="moderate", locks=0, seed=PINNED_SEED,
            output=str(tmp_path), ter_version=2,
            no_validate=False,
        )
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    def test_no_validate_builds_broken_seed(self, tmp_path):
        import main
        main.cmd_generate(self._args(tmp_path, no_validate=True))
        # task 19.4: the zone id (the per-build directory) is
        # new_zone_id(prefix=<name>) = cli_<ts>_<hex6>, so two runs with the
        # same name land in different directories (Req 8.3). Every artifact
        # inside is still named by the Build_Name stem "cli", and the spec is
        # saved as <name>.json IN the build directory (not flat).
        build_dirs = [p for p in tmp_path.iterdir()
                      if p.is_dir() and p.name.startswith("cli_")]
        assert len(build_dirs) == 1, f"expected one cli_* build dir, got {build_dirs}"
        bd = build_dirs[0] / "v1"
        assert (bd / "cli.eqg").exists()
        assert (bd / "cli.json").exists()

    def test_gate_blocks_pinned_bad_seed(self, tmp_path, monkeypatch):
        # Force the CLI to build a broken zone (an isolated, corridor-less room)
        # so the pinned-seed gate must error out. No seed is reliably broken any
        # more, so we inject the breakage rather than rely on one.
        #
        # The CLI builds its spec through ``ai.expand.plan_to_spec`` (the shared
        # controls path), which drives ``LayoutGenerator`` imported into the
        # ``ai.expand`` namespace — so that is where the breakage is injected.
        import main  # noqa: F401  (keeps the CLI import alive for the run)
        import ai.expand as _expand
        from generators.layout import LayoutGenerator as _RealLG

        class _BrokenLG(_RealLG):
            def generate(self, *a, **k):
                spec = super().generate(*a, **k)
                spec.rooms.append(RoomSpec(
                    id="isolated", center_x=100_000.0, center_y=100_000.0,
                    floor_z=0.0, width=200, depth=200, height=100))
                return spec

        monkeypatch.setattr(_expand, "LayoutGenerator", _BrokenLG)
        with pytest.raises(SystemExit) as ei:
            main.cmd_generate(self._args(tmp_path, no_validate=False))
        assert ei.value.code == 1


# ---------------------------------------------------------------------------
# CLI argument handling (M0 6.8, 6.9)
# ---------------------------------------------------------------------------

class TestCliArgs:
    def test_legacy_theme_outdoor_equivalent_to_zone_type_wilderness(self):
        """CLI legacy alias resolves ``--theme outdoor`` to the SAME zone type
        as ``--zone-type wilderness``, and both are accepted now that
        wilderness is enabled (Req 3.3, 11.3).

        ``--theme`` is the kept legacy alias on the CLI; it shares the
        ``zone_type`` argparse dest and its value is converted by
        ``_zone_type_arg``.
        """
        import main

        assert main._zone_type_arg("outdoor") == "wilderness"
        assert main._zone_type_arg("wilderness") == "wilderness"

    def test_cave_theme_rejected_by_argparse(self, tmp_path):
        # "cave" is not a defined zone type: _zone_type_arg can't canonicalise
        # it, so argparse exits 2 in parse_args, before any build, and no output
        # directory is created. Driven in-process via main(argv).
        import main
        out = str(tmp_path / "cli_out")
        with pytest.raises(SystemExit) as ei:
            main.main(["generate", "x", "--theme", "cave", "--output", out])
        assert ei.value.code == 2
        assert not Path(out).exists()

    def test_output_inside_eq_path_exits_2_naming_both(
            self, tmp_path, monkeypatch, capsys):
        """CLI refuses an output dir that overlaps EQ_PATH (Req 10.2, task 19.5).

        With ``EQ_PATH`` set (via ``env_value``) to a directory that CONTAINS
        the requested ``--output``, ``main()`` runs ``assert_output_allowed``
        right after parsing and exits 2 BEFORE any build/write — the error names
        BOTH the output path and the EQ install, and no output directory is
        created.
        """
        import main

        eq = tmp_path / "everquest_rof2"
        out = eq / "mygen" / "output"      # output resolves INSIDE the EQ install
        eq.mkdir()
        monkeypatch.setenv("EQ_PATH", str(eq))

        with pytest.raises(SystemExit) as ei:
            main.main(["generate", "refuse", "--rooms", "3",
                       "--output", str(out)])
        assert ei.value.code == 2
        err = capsys.readouterr().err
        # The refusal names BOTH paths.
        assert str(out.resolve()) in err
        assert str(eq.resolve()) in err
        # Nothing was built under the (refused) output path.
        assert not out.exists()

    def test_output_disjoint_from_eq_path_is_allowed(
            self, tmp_path, monkeypatch):
        """A normal output dir that does NOT overlap EQ_PATH builds normally.

        The refusal check must not disturb the ordinary case: with EQ_PATH set
        to a disjoint sibling, a small dungeon build runs to completion and
        lands its artifacts under the per-build directory (Req 10.1/10.2 — the
        guard is plumbing, not a behaviour change).
        """
        import main

        eq = tmp_path / "everquest_rof2"
        out = tmp_path / "output"          # disjoint sibling of the EQ install
        eq.mkdir()
        monkeypatch.setenv("EQ_PATH", str(eq))

        main.main(["generate", "okgen", "--rooms", "3", "--seed",
                   str(GOOD_SEED), "--output", str(out)])

        build_dirs = [p for p in out.iterdir()
                      if p.is_dir() and p.name.startswith("okgen_")]
        assert build_dirs, "a disjoint output dir should build normally"

    # -- Geometry-slice CLI options (task 17.8) ---------------------------
    #
    # The range-checked type= functions and _zone_type_arg (main.py, task 17.7)
    # reject an out-of-domain geometry-slice option DURING parse_args, so
    # argparse exits 2 before cmd_generate runs and before any output directory
    # is created. Each case is driven in-process via main(argv) and asserts the
    # exit code AND that no output dir was written (the write only happens after
    # a successful parse). "cave" is undefined and rejected by _zone_type_arg;
    # the numeric options
    # are rejected by their range-checked converters.

    @pytest.mark.parametrize("bad_arg", [
        ["--zone-type", "cave"],        # undefined zone type
        ["--rooms", "0"],               # below the 1..30 range
        ["--rooms", "31"],              # above the 1..30 range
        ["--locks", "6"],               # above the 0..5 range
        ["--seed", "-1"],               # below the 0..2^31-1 range
        ["--seed", "2147483648"],       # above the 0..2^31-1 range (2^31)
    ])
    def test_out_of_domain_option_exits_2_and_writes_nothing(
            self, tmp_path, bad_arg):
        import main
        out = str(tmp_path / ("o_" + "_".join(bad_arg).replace("-", "")))
        with pytest.raises(SystemExit) as ei:
            main.main(["generate", "x", *bad_arg, "--output", out])
        assert ei.value.code == 2, (
            f"{bad_arg} should exit 2 (out of domain), got {ei.value.code}")
        # argparse exits during parse_args, before cmd_generate creates the dir.
        assert not Path(out).exists()

    def test_verticality_flat_builds_a_flat_zone(self, tmp_path):
        """``--verticality flat`` builds a zone with NO elevation.

        The controls path sends ``verticality: "flat"`` through
        ``ZonePlan.from_controls`` -> ``plan_to_spec``, which generates with
        ``elevation=False`` and zero elevation chance, so every room shares a
        single floor height. We run the real CLI build (small dungeon, kept
        fast) and assert the saved spec's rooms are all at one ``floor_z`` —
        the structural signature of a flat zone.
        """
        import argparse
        import main
        from generators.zone_spec import ZoneSpec

        ns = argparse.Namespace(
            name="flatcli", zone_type="dungeon", rooms=4, size="small",
            verticality="flat", locks=0, seed=GOOD_SEED,
            output=str(tmp_path), ter_version=2, no_validate=False,
        )
        main.cmd_generate(ns)

        # task 19.4: the spec is saved as <name>.json inside the per-build
        # directory <output>/<zone_id>/v1/, where <zone_id> = flatcli_<ts>_<hex6>.
        build_dirs = [p for p in tmp_path.iterdir()
                      if p.is_dir() and p.name.startswith("flatcli_")]
        assert len(build_dirs) == 1, f"expected one flatcli_* dir, got {build_dirs}"
        spec = ZoneSpec.load(build_dirs[0] / "v1" / "flatcli.json")
        floors = {round(r.floor_z, 6) for r in spec.rooms}
        assert spec.rooms, "expected rooms in the built spec"
        assert len(floors) == 1, (
            f"flat zone should have one floor height, got {sorted(floors)}")

    def test_cli_controls_plan_equals_server_controls_plan(self):
        """The CLI's controls plan EQUALS the Server's controls plan (Req 1.2).

        Both surfaces funnel the geometry slice through the exact same
        ``ZonePlan.from_controls`` entry point, so for identical
        zone_type/rooms/size/verticality/locks (and the same pinned seed, which
        the plan itself does not carry — it is applied later by the pipeline)
        the two produced plans must be field-for-field equal. This pins that the
        CLI and Server cannot drift into two different controls interpretations.
        """
        from ai.schema import ZonePlan

        for zone_type, rooms, size, verticality, locks, seed in [
            ("dungeon", 5, "medium", "moderate", 0, 7),
            ("city", 12, "large", "flat", 3, 1955208177),
            ("dungeon", 1, "small", "dramatic", 5, 0),
            ("city", 30, "huge", "moderate", 2, 2147483647),
        ]:
            # The dict the CLI builds (main.cmd_generate), seed applied later.
            cli_controls = {
                "zone_type": zone_type,
                "rooms": rooms,
                "size": size,
                "verticality": verticality,
                "locks": locks,
            }
            # The dict the Server builds in controls mode (server/app.py): the
            # same geometry slice (keys equal here by construction of identical
            # client input).
            server_controls = {
                "zone_type": zone_type,
                "rooms": rooms,
                "size": size,
                "verticality": verticality,
                "locks": locks,
            }

            cli_plan = ZonePlan.from_controls(cli_controls)
            cli_plan.name = "cli"
            server_plan = ZonePlan.from_controls(server_controls)
            server_plan.name = "cli"   # name is per-build, not a controls value

            assert cli_plan.to_dict() == server_plan.to_dict(), (
                f"CLI/Server controls plans diverged for "
                f"{zone_type}/{rooms}/{size}/{verticality}/{locks}/seed {seed}")

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
        fall back to box and emit a ``backend_fallback`` warning. The gate is
        switched off so the build runs once; the pipeline merges ``result.warnings`` into both ``vb.warnings`` and the
        written Sidecar (Req 4.3)."""
        from generators.backends import TerrainBackend

        monkeypatch.setattr(TerrainBackend, "build",
                            lambda self, spec, ter_name, ter_version: None)

        def factory(seed):
            return LayoutGenerator(zone_type="wilderness", seed=GOOD_SEED).generate(
                "pipe", room_count=5)

        vb = _run(factory, tmp_path, zone_type="wilderness",
                  gated_zone_types=frozenset(), max_attempts=8)

        # Ungated, built once via the box fallback.
        assert vb.validated is False
        assert vb.result.backend == "box"

        fallback = "backend_fallback: terrain unavailable, built with box"
        assert fallback in vb.warnings

        data = self._sidecar(vb)
        assert fallback in data["warnings"]


# ---------------------------------------------------------------------------
# Confinement, key-leak and Build_Name example tests (task 20.8)
# ---------------------------------------------------------------------------
#
# Deterministic examples pinning the wave-6 confinement / no-key-leak / naming
# invariants (Req 8.2, 9.4, 10.2). These are the concrete companions to the
# Property-15 writes-confined audit-hook test (task 20.7): where that proves the
# invariant over many inputs, these pin the exact behaviours a human would check.


class TestConfinementExample:
    """Req 10.2 — with EQ_PATH overlapping the Output_Directory the tool refuses.

    Two entry points, one invariant: the CLI exits 2 (naming BOTH paths) and
    importing ``server.app`` raises ``OutsideOutputError``. The server half runs
    the import in a FRESH subprocess with the overlapping EQ_PATH env set, so the
    already-imported module in this test process is not disturbed (the refusal
    fires only at import time, before ``OUTPUT_DIR.mkdir``).
    """

    def test_output_inside_eq_path_refuses_cli_and_server_import(
            self, tmp_path, monkeypatch, capsys):
        import main

        # EQ_PATH is an install dir; the requested --output resolves INSIDE it.
        eq = tmp_path / "everquest_rof2"
        out = eq / "gen" / "output"
        eq.mkdir()

        # --- CLI half: exit 2, naming BOTH the output path and the EQ install,
        # nothing written.
        monkeypatch.setenv("EQ_PATH", str(eq))
        with pytest.raises(SystemExit) as ei:
            main.main(["generate", "refuse", "--rooms", "3",
                       "--output", str(out)])
        assert ei.value.code == 2
        err = capsys.readouterr().err
        assert str(out.resolve()) in err, err
        assert str(eq.resolve()) in err, err
        assert not out.exists(), "a refused build must write nothing"

        # --- Server half: importing server.app with an EQ_PATH that CONTAINS
        # the server's OUTPUT_DIR raises OutsideOutputError at import time. Run
        # it in a fresh subprocess (the module is already imported here) with
        # EQ_PATH = repo root, which contains the server's output/web dir.
        import subprocess
        import sys
        import os
        import server.app as app_mod

        repo_root = Path(app_mod.__file__).resolve().parent.parent
        env = dict(os.environ)
        env["EQ_PATH"] = str(repo_root)      # contains output/web -> overlap

        proc = subprocess.run(
            [sys.executable, "-c", "import server.app"],
            cwd=str(repo_root), env=env, capture_output=True, text=True,
        )
        assert proc.returncode != 0, (
            "server.app import should fail with an overlapping EQ_PATH")
        assert "OutsideOutputError" in proc.stderr, proc.stderr


class TestKeyNeverLeaks:
    """Req 10.2 — an API key in the environment never leaks into any artifact,
    response, captured log or stdout/stderr.

    Sentinel key values are placed in the environment and the planner / texture
    provider are pinned to their zero-network paths (rule planner + procedural
    textures), so NO real API call is made. One prompt generate (Server) and one
    CLI generate are then run, and the sentinel string must appear in NO output
    file, NO response body, NO captured log and NO stdout/stderr. This is the
    log-redaction (task 19.2) + ``env_value`` not echoing keys, pinned.
    """

    SENTINEL = "sk-SENTINEL-do-not-leak-0123456789"

    def _set_sentinel_env(self, monkeypatch):
        # Keys present in the env (sentinel values) ...
        monkeypatch.setenv("OPENAI_API_KEY", self.SENTINEL)
        monkeypatch.setenv("ANTHROPIC_API_KEY", self.SENTINEL)
        monkeypatch.setenv("STABILITY_API_KEY", self.SENTINEL)
        # ... but force the zero-network paths so no real request is made.
        monkeypatch.setenv("EQ_S3D_PLANNER", "rule")
        monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "procedural")
        # Reset forced globals so the overrides above are honoured.
        import ai.planner
        import generators.textures.factory as texture_factory
        ai.planner.set_planner(None)
        texture_factory.set_provider(None)

    @staticmethod
    def _assert_tree_clean(root: Path, needle: str):
        """No file under ``root`` may contain ``needle`` (text or bytes)."""
        needle_b = needle.encode("utf-8")
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            data = p.read_bytes()
            assert needle_b not in data, (
                f"sentinel key leaked into output file {p}")

    def test_sentinel_key_never_leaks_through_prompt_or_cli(
            self, tmp_path, monkeypatch, capsys, caplog, no_network):
        import logging
        import main
        import server.app as app_mod
        from fastapi.testclient import TestClient

        self._set_sentinel_env(monkeypatch)
        caplog.set_level(logging.DEBUG)

        # --- Server: one prompt generate (rule planner, procedural textures).
        server_out = tmp_path / "server"
        server_out.mkdir()
        monkeypatch.setattr(app_mod, "OUTPUT_DIR", server_out)
        monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "server_fail.jsonl")

        client = TestClient(app_mod.app)
        resp = client.post(
            "/api/generate",
            json={"prompt": "a dark dungeon with a few rooms"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["planner"] == "rule", body       # zero-network path
        # The sentinel must not be anywhere in the response body.
        assert self.SENTINEL not in resp.text, "sentinel leaked into the response"

        # --- CLI: one generate on the default gated dungeon.
        cli_out = tmp_path / "cli"
        main.main(["generate", "keysafe", "--rooms", "4", "--output", str(cli_out)])

        # No output file (either tree) contains the sentinel.
        self._assert_tree_clean(server_out, self.SENTINEL)
        self._assert_tree_clean(cli_out, self.SENTINEL)

        # No captured stdout/stderr and no captured log record contains it.
        captured = capsys.readouterr()
        assert self.SENTINEL not in captured.out, "sentinel leaked to stdout"
        assert self.SENTINEL not in captured.err, "sentinel leaked to stderr"
        assert self.SENTINEL not in caplog.text, "sentinel leaked into a log record"

        # And it was never used to open a foreign connection.
        assert no_network == [], f"a key path attempted network: {no_network}"


class TestBuildNameExample:
    """Req 8.2 — the CLI Build_Name alphabet and lower-casing, by example.

    A positional with a hyphen is out of the ``[a-z0-9_]+`` Build_Name alphabet
    and must exit 2 during parse (before any build/write); a mixed-case
    ``MyZone`` is lower-cased to ``myzone`` and names every artifact
    ``myzone.*``.
    """

    def test_hyphenated_name_exits_2_and_writes_nothing(self, tmp_path):
        import main
        out = str(tmp_path / "out")
        with pytest.raises(SystemExit) as ei:
            main.main(["generate", "bad-name", "--rooms", "3", "--output", out])
        assert ei.value.code == 2, "a hyphenated Build_Name must exit 2"
        # argparse exits during parse_args, before cmd_generate creates the dir.
        assert not Path(out).exists()

    def test_mixed_case_name_builds_lowercased_artifacts(self, tmp_path):
        import main
        out = tmp_path / "out"
        main.main(["generate", "MyZone", "--rooms", "3", "--seed",
                   str(GOOD_SEED), "--output", str(out)])

        # The per-build directory is new_zone_id(prefix=<name>) on the
        # lower-cased name, so it starts with "myzone_" (never "MyZone_").
        build_dirs = [p for p in out.iterdir()
                      if p.is_dir() and p.name.startswith("myzone_")]
        assert len(build_dirs) == 1, (
            f"expected one myzone_* build dir, got {list(out.iterdir())}")
        assert not any(p.name.startswith("MyZone") for p in out.iterdir()), (
            "the Build_Name must be lower-cased, not kept mixed-case")

        bd = build_dirs[0] / "v1"
        # Every artifact carries the lower-cased Build_Name stem "myzone".
        for artifact in ("myzone.eqg", "myzone.glb", "myzone.zone.json",
                         "myzone.map.svg", "myzone.json"):
            assert (bd / artifact).exists(), f"missing {artifact} in {bd}"
