"""Known short names (step 17 task 1, Requirement 1.1; umbrella 8.1-8.4 as amended by A1/A2).

- The committed list holds ``arena`` and the classic zones and no companion archive.
- ``in_install`` is false for every entry with no install; with the install ``arena`` is true
  (skips when the install is absent).
- The scan rules, on a fake install of tiny archives.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyzer import zonelist
from analyzer.zonelist import DATA_PATH, DEFAULT_TARGET, closest, is_known, known_shortnames
from core.env import env_value
from core.pfs import PfsArchive

INSTALL = Path(env_value("EQ_PATH") or r"F:\everquest_rof2")


@pytest.fixture(autouse=True)
def _fresh_cache():
    zonelist._cache.clear()
    yield
    zonelist._cache.clear()


def test_committed_list_holds_the_classic_zones_and_no_companion():
    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))["zones"]
    names = [r["shortname"] for r in rows]
    assert len(names) == len(set(names))
    for short in ("arena", "qeynos", "freporte", "befallen", "blackburrow", "crushbone"):
        assert short in names
    assert not [n for n in names if zonelist.is_companion(n)]
    assert not [n for n in names if n.endswith(("_obj", "_chr")) or n.startswith("gequip")]
    assert {r["container"] for r in rows} <= {"s3d", "eqg"}
    assert set(rows[0]) == {"shortname", "long_name", "container"}   # no zone id (A1)
    assert DEFAULT_TARGET == "arena"


def test_no_install_means_nothing_is_in_install(monkeypatch, tmp_path):
    monkeypatch.setenv("EQ_PATH", str(tmp_path / "no_install_here"))
    zones = known_shortnames()
    assert zones and not any(z.in_install for z in zones.values())
    assert is_known("ARENA") and is_known(" Arena ") and not is_known("gen_x")
    assert "arena" in closest("arenna")


@pytest.mark.skipif(not (INSTALL / "arena.eqg").exists(), reason="EQ install not present (set EQ_PATH)")
def test_install_marks_arena_in_install():
    zones = known_shortnames(INSTALL)
    assert zones["arena"].in_install
    assert sum(z.in_install for z in zones.values()) > len(zones) // 2


def _pfs(path: Path, *names: str) -> None:
    a = PfsArchive()
    for n in names:
        a.add(n, b"x")
    a.write_file(path)


def test_scan_rules_on_a_fake_install(tmp_path):
    _pfs(tmp_path / "oldzone.s3d", "oldzone.wld", "objects.wld")
    _pfs(tmp_path / "oldzone_obj.s3d", "oldzone_obj.wld")
    _pfs(tmp_path / "oldzone_chr.s3d", "oldzone_chr.wld")
    _pfs(tmp_path / "gequip.s3d", "gequip.wld")
    _pfs(tmp_path / "notazone.s3d", "other.wld")
    _pfs(tmp_path / "newzone.eqg", "ter_newzone.ter")
    _pfs(tmp_path / "zonzone.eqg", "zonzone.zon")
    _pfs(tmp_path / "loosezon.eqg", "thing.mod")
    (tmp_path / "loosezon.zon").write_bytes(b"EQGZ")
    _pfs(tmp_path / "props.eqg", "thing.mod")
    _pfs(tmp_path / "both.s3d", "both.wld")
    _pfs(tmp_path / "both.eqg", "ter_both.ter")
    assert zonelist.scan_install(tmp_path) == {
        "oldzone": "s3d", "newzone": "eqg", "zonzone": "eqg", "loosezon": "eqg", "both": "eqg"}
