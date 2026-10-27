"""
tests/test_rof2check.py
-----------------------
Focused unit tests for the RoF2 Format_Checker (``analyzer/rof2check.py``,
task 20.2).

Two example cases — the full Property 8 (every enabled build passes) and
Property 14 (totality / specificity fuzzing) live in tasks 20.4 / 20.5:

  * A VALID built dungeon ``.eqg`` → ``report.passed`` is True, every one of the
    eleven checks is present in canonical order, there is NO ``normals_resolve``
    check, and ``name_consistent`` passes.
  * A corrupt / garbage ``.eqg`` → ``check_eqg`` does NOT raise, ``report.passed``
    is False, ``pfs_reads`` failed with a message that names it, every check is
    still present, and the checks that depend on the unreadable archive are
    marked skipped (dependent-of-an-unreadable-input).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ai.expand import plan_to_spec
from ai.rule_planner import RulePlanner
from analyzer.rof2check import (
    CHECK_NAMES,
    FormatCheck,
    FormatReport,
    check_eqg,
)
from generators.builder import ZoneBuilder
from generators.zone_spec import ZoneSpec


EXPECTED_CHECKS = (
    "pfs_reads",
    "required_files",
    "ter_roundtrip",
    "zon_roundtrip",
    "zon_model_ref",
    "material_indices",
    "diffuse_textures",
    "collision_policy",
    "safe_point",
    "bounds_sane",
    "name_consistent",
)


@pytest.fixture(scope="module")
def valid_dungeon():
    """Build a small valid dungeon ``.eqg`` once and hand back its path + spec."""
    with tempfile.TemporaryDirectory() as d:
        plan = RulePlanner().plan("create a dungeon with 6 rooms")
        spec = plan_to_spec(plan, 7)
        spec.name = "checkme"
        result = ZoneBuilder(spec).build(output_dir=d, write_glb=False)
        sidecar = Path(d) / "checkme.zone.json"
        yield Path(result.eqg_path), spec, sidecar


def _names(report: FormatReport) -> list[str]:
    return [c.name for c in report.checks]


# ---------------------------------------------------------------------------
# Valid build
# ---------------------------------------------------------------------------

def test_valid_build_passes(valid_dungeon):
    eqg, spec, sidecar = valid_dungeon
    report = check_eqg(eqg, spec, sidecar_path=sidecar)

    assert isinstance(report, FormatReport)
    assert report.passed is True, f"unexpected failures: {report.messages}"
    assert report.failed_checks == []


def test_valid_build_has_all_checks_in_order(valid_dungeon):
    eqg, spec, sidecar = valid_dungeon
    report = check_eqg(eqg, spec, sidecar_path=sidecar)

    assert _names(report) == list(EXPECTED_CHECKS)
    # CHECK_NAMES is the single source of truth and matches the expected set.
    assert tuple(CHECK_NAMES) == EXPECTED_CHECKS


def test_valid_build_has_no_normals_resolve(valid_dungeon):
    eqg, spec, sidecar = valid_dungeon
    report = check_eqg(eqg, spec, sidecar_path=sidecar)

    assert "normals_resolve" not in _names(report)


def test_valid_build_name_consistent_passes(valid_dungeon):
    eqg, spec, sidecar = valid_dungeon
    report = check_eqg(eqg, spec, sidecar_path=sidecar)

    nc = next(c for c in report.checks if c.name == "name_consistent")
    assert nc.passed is True
    assert nc.skipped is False


def test_valid_build_to_dict_shape(valid_dungeon):
    eqg, spec, sidecar = valid_dungeon
    report = check_eqg(eqg, spec, sidecar_path=sidecar)

    d = report.to_dict()
    assert set(d) == {"passed", "checks"}
    assert d["passed"] is True
    assert [c["name"] for c in d["checks"]] == list(EXPECTED_CHECKS)
    for c in d["checks"]:
        assert set(c) >= {"name", "passed", "messages"}


# ---------------------------------------------------------------------------
# Corrupt build — totality
# ---------------------------------------------------------------------------

def _corrupt_eqg(tmp: Path) -> Path:
    p = tmp / "garbage.eqg"
    p.write_bytes(b"this is not a PFS archive, just random bytes" * 20)
    return p


def test_corrupt_build_does_not_raise(tmp_path):
    spec = ZoneSpec(name="checkme", zone_type="dungeon")
    report = check_eqg(_corrupt_eqg(tmp_path), spec)  # must not raise
    assert isinstance(report, FormatReport)


def test_corrupt_build_fails_with_pfs_reads_message(tmp_path):
    spec = ZoneSpec(name="checkme", zone_type="dungeon")
    report = check_eqg(_corrupt_eqg(tmp_path), spec)

    assert report.passed is False
    pfs = next(c for c in report.checks if c.name == "pfs_reads")
    assert pfs.passed is False
    assert pfs.messages, "pfs_reads should carry a reason"
    assert all(m.startswith("pfs_reads:") for m in pfs.messages)


def test_corrupt_build_has_every_check_present(tmp_path):
    spec = ZoneSpec(name="checkme", zone_type="dungeon")
    report = check_eqg(_corrupt_eqg(tmp_path), spec)

    assert _names(report) == list(EXPECTED_CHECKS)
    assert "normals_resolve" not in _names(report)


def test_corrupt_build_dependents_are_skipped(tmp_path):
    spec = ZoneSpec(name="checkme", zone_type="dungeon")
    report = check_eqg(_corrupt_eqg(tmp_path), spec)

    by_name = {c.name: c for c in report.checks}

    # pfs_reads is the independent root cause: it RAN and failed (not skipped).
    assert by_name["pfs_reads"].skipped is False
    assert by_name["pfs_reads"].passed is False

    # required_files is independent too — it inspects the (empty) entry list and
    # fails by naming the missing files, rather than skipping.
    assert by_name["required_files"].skipped is False
    assert by_name["required_files"].passed is False

    # Every check that needs the unreadable archive/TER/ZON is skipped; each
    # skipped check also fails and names its failed dependency.
    skipped = [c for c in report.checks if c.skipped]
    assert {c.name for c in skipped} == set(EXPECTED_CHECKS) - {"pfs_reads", "required_files"}
    for c in skipped:
        assert c.passed is False
        assert c.messages and c.messages[0].startswith(f"{c.name}: skipped")


def test_missing_archive_does_not_raise(tmp_path):
    spec = ZoneSpec(name="checkme", zone_type="dungeon")
    report = check_eqg(tmp_path / "does_not_exist.eqg", spec)

    assert report.passed is False
    assert _names(report) == list(EXPECTED_CHECKS)
    pfs = next(c for c in report.checks if c.name == "pfs_reads")
    assert pfs.passed is False
