"""The exported archive and files (step 17 task 3; Req 2, umbrella 8.7, 8.8, 8.10-8.12,
8.14, 9.7).

One build per zone type through the pipeline (gate off, as ``test_handoffs``), each
exported to ``arena`` and to a second short name. An Export renames, it never rebuilds:
the entries, ZON and map files are the build's under new names, the CRCs are EQ's for
those names, and the build's own files never change."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import generators.export as ex
from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.rof2check import check_eqg
from analyzer.zonelist import closest, is_known
from core.pfs import PfsArchive, _filename_crc32, read_directory
from core.ter import TerFile
from core.zon import ZonFile
from generators.export import EXPORT_DIR, UnknownShortname, export_build, resolve_shortname
from generators.pipeline import generate_validated

ZONE_TYPES = ("dungeon", "city", "wilderness", "outdoor_dungeon")
SEED = 3
SECOND = "befallen"


def _plan(zone_type: str) -> ZonePlan:
    plan = ZonePlan(name=f"ex_{zone_type}", zone_type=zone_type)
    plan.validate()
    return plan


def _hashes(build_dir: Path) -> dict:
    """sha256 of every file of the build (the export folder excluded)."""
    skip = build_dir / EXPORT_DIR
    return {str(p.relative_to(build_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(build_dir.rglob("*")) if p.is_file() and skip not in p.parents}


def _folder(d: Path) -> dict:
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def exports(tmp_path_factory):
    assert is_known(SECOND)
    out = tmp_path_factory.mktemp("export")
    done = {}
    for zt in ZONE_TYPES:
        vb = generate_validated(lambda s, zt=zt: plan_to_spec(_plan(zt), seed=s), zone_type=zt,
                                zone_id=f"ex_{zt}", seed=SEED, output_dir=out, write_glb=False,
                                validate_enabled=False, failure_log=None)
        before = _hashes(vb.build_dir)
        first = export_build(vb.build_dir)
        first_files = _folder(first.dir)
        second = export_build(vb.build_dir, SECOND.upper(), clear_spawns=True)
        done[zt] = dict(vb=vb, before=before, after=_hashes(vb.build_dir),
                        first=first, first_files=first_files, second=second)
    return done


@pytest.fixture(params=ZONE_TYPES)
def one(request, exports):
    return exports[request.param]


@pytest.mark.parametrize("which, short", [("first", "arena"), ("second", SECOND)])
def test_archive_is_the_build_renamed(one, which, short):
    vb, res = one["vb"], one[which]
    name = vb.spec.name.lower()
    assert res.shortname == short and res.dir == vb.build_dir.resolve() / EXPORT_DIR / short
    assert res.format.passed, res.format.messages
    assert res.sql_written is False

    src = {f.name: f.data for f in PfsArchive.from_file(vb.result.eqg_path).files}
    got = {f.name: f.data for f in PfsArchive.from_file(res.eqg_path).files}
    renamed = {f"ter_{name}.ter": f"ter_{short}.ter", f"{name}.zon": f"{short}.zon"}
    assert sorted(got) == sorted(renamed.get(n, n) for n in src)
    for n, data in src.items():
        if n != f"{name}.zon":
            assert got[renamed.get(n, n)] == data, n          # byte-identical (TER included)

    # Every CRC is EQ's for the entry's (new) name.
    entries, errors = read_directory(res.eqg_path.read_bytes())
    assert not errors
    named = [e for e in entries if e.name is not None]
    assert len(named) == len(src)
    assert all(e.crc == _filename_crc32(e.name) for e in named)

    # The ZON: the terrain reference is the short name's, everything else as built.
    old = ZonFile.from_bytes(src[f"{name}.zon"])
    new = ZonFile.from_bytes(got[f"{short}.zon"])
    assert new.models[0] == f"TER_{short.upper()}.TER"
    assert new.models[1:] == old.models[1:]
    assert (new.objects, new.regions, new.lights) == (old.objects, old.regions, old.lights)

    # Read back: same vertices, polygons, materials (8.11).
    a = TerFile.from_bytes(src[f"ter_{name}.ter"])
    b = TerFile.from_bytes(got[f"ter_{short}.ter"])
    assert (a.vertices, a.polygons, a.materials) == (b.vertices, b.polygons, b.materials)


@pytest.mark.parametrize("which, short", [("first", "arena"), ("second", SECOND)])
def test_map_files_and_sidecar(one, which, short):
    vb, res = one["vb"], one[which]
    name = vb.spec.name.lower()
    src_maps = sorted((vb.build_dir / "maps").glob("*.txt"))
    assert src_maps
    for p in src_maps:
        q = res.dir / "maps" / (short + p.name[len(name):])
        assert q.read_bytes() == p.read_bytes()
    assert sorted(p.name for p in (res.dir / "maps").iterdir()) == sorted(
        short + p.name[len(name):] for p in src_maps)

    built = json.loads(vb.result.sidecar_path.read_text(encoding="utf-8"))
    side = json.loads(res.sidecar_path.read_text(encoding="utf-8"))
    assert side["shortname"] == short and side["name"] == built["name"]
    assert side["export"] == {"shortname": short, "build": name,
                              "clear_spawns": which == "second"}
    assert all(f.startswith(f"maps/{short}") for f in side["map_files"] if f.startswith("maps/"))
    for k in set(built) - {"map_files", "outline"}:
        assert side[k] == built[k], k


def test_build_unchanged_and_exports_apart(one):
    assert one["after"] == one["before"]
    first, second = one["first"], one["second"]
    assert first.dir != second.dir
    assert _folder(first.dir) == one["first_files"]          # the second overwrote nothing
    assert {p.parent for p in first.files} & {p.parent for p in second.files} == set()


def test_repeat_export_replaces_its_folder(exports, tmp_path):
    vb = exports["dungeon"]["vb"]
    stray = vb.build_dir / EXPORT_DIR / "arena" / "stray.txt"
    stray.write_text("x")
    before = _hashes(vb.build_dir)
    res = export_build(vb.build_dir, "arena")
    assert not stray.exists() and res.format.passed
    assert _hashes(vb.build_dir) == before


def test_shortname_rules():
    assert resolve_shortname(None) == "arena"
    assert resolve_shortname("") == "arena"
    assert resolve_shortname("   ") == "arena"
    assert resolve_shortname("ARENA") == "arena"
    assert resolve_shortname(" Befallen ") == "befallen"


def test_unknown_name_names_it_and_close_names(exports):
    vb = exports["city"]["vb"]
    before = _folder(vb.build_dir)
    with pytest.raises(UnknownShortname) as info:
        export_build(vb.build_dir, "arenna")
    err = info.value
    assert "arenna" in str(err) and err.shortname == "arenna"
    assert 1 <= len(err.close) <= 5 and "arena" in err.close
    assert err.close == closest("arenna")
    assert all(n in str(err) for n in err.close)
    assert _folder(vb.build_dir) == before                      # nothing written


def test_check_uses_the_short_name(exports, tmp_path):
    """The exported archive fails the build-time check and a check for another name; a
    name off the Known_Zone_List fails ``name_consistent`` (9.7 second half)."""
    vb, res = exports["dungeon"]["vb"], exports["dungeon"]["first"]
    spec = vb.spec

    def failed(report):
        return {c.name for c in report.checks if not c.passed}

    assert failed(check_eqg(res.eqg_path, spec, sidecar_path=res.sidecar_path,
                            expected_name="ARENA")) == set()
    assert "name_consistent" in failed(check_eqg(res.eqg_path, spec, expected_name=SECOND))
    assert "name_consistent" in failed(check_eqg(res.eqg_path, spec))
    # The build itself still passes the unchanged build-time check.
    assert check_eqg(vb.result.eqg_path, spec, sidecar_path=vb.result.sidecar_path).passed

    # A name off the list, even with every name in the archive matching it.
    arc = ex.export_archive(PfsArchive.from_file(vb.result.eqg_path), spec.name.lower(), "zzznotazone")
    path = tmp_path / "zzznotazone.eqg"
    arc.write_file(path)
    report = check_eqg(path, spec, expected_name="zzznotazone")
    (msg,) = [c for c in report.checks if c.name == "name_consistent"][0].messages
    assert "not on the Known_Zone_List" in msg and failed(report) == {"name_consistent"}


def test_a_failed_check_writes_no_sql(exports, monkeypatch):
    vb = exports["city"]["vb"]
    calls = []
    monkeypatch.setattr(ex, "_after_check", lambda *a: calls.append(a))
    real = ex.check_eqg

    def broken(path, spec, **kw):
        report = real(path, spec, **kw)
        report.passed = False
        return report

    monkeypatch.setattr(ex, "check_eqg", broken)
    res = export_build(vb.build_dir, "arena")
    assert not res.format.passed and res.sql_written is False and calls == []
    monkeypatch.setattr(ex, "check_eqg", real)
    assert export_build(vb.build_dir, "arena").format.passed and len(calls) == 1
