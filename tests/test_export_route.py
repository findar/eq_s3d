"""The Export route, bundle and CLI (step 17 task 6; Req 1.2, 4.1, 4.3, 4.4).

One dungeon build with locks, in the server's own output folder: exported to ``arena``
through ``POST /api/export``, every file and the bundle downloaded through the export file
route, then the same Export through ``main.py export``."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

import main as cli
import server.app as app_mod
from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.zonelist import closest, known_shortnames
from generators.export import EXPORT_DIR, MOVE_ASIDE
from generators.pipeline import generate_validated

ZONE = "exroute"
SEED = 3


def _files(d):
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*"))
            if p.is_file()}


def _same(name, data):
    """``data`` with its write time dropped: an ``.eqg``'s footer (lessons-learned), and
    each entry of a bundle the same way."""
    if name.endswith(".eqg"):
        return data[:-4]
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return [(n, _same(n, z.read(n))) for n in z.namelist()]
    return data


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("exroute") / "web"
    root.mkdir()
    mp.setattr(app_mod, "OUTPUT_DIR", root)
    plan = ZonePlan(name=ZONE, zone_type="dungeon", locks=2)
    plan.validate()
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon",
                            zone_id=ZONE, seed=SEED, output_dir=root, write_glb=False,
                            validate_enabled=False, failure_log=None)
    assert vb.build_dir == (root / ZONE / "v1").resolve() or vb.build_dir == root / ZONE / "v1"
    yield TestClient(app_mod.app), vb
    mp.undo()


@pytest.fixture(scope="module")
def exported(server):
    client, vb = server
    before = {k: v for k, v in _files(vb.build_dir).items() if not k.startswith(EXPORT_DIR)}
    r = client.post("/api/export", json={"zone": ZONE, "version": 1})
    assert r.status_code == 200, r.text
    return client, vb, before, r.json()


def test_shortnames():
    client = TestClient(app_mod.app)
    body = client.get("/api/shortnames").json()
    assert body["default"] == "arena"
    names = [z["shortname"] for z in body["zones"]]
    assert sorted(names) == sorted(known_shortnames())
    assert set(body["zones"][0]) == {"shortname", "long_name", "container", "in_install"}
    flags = [z["in_install"] for z in body["zones"]]
    assert flags == sorted(flags, reverse=True)                  # installed first


def test_export_and_download_every_file(exported):
    client, vb, before, body = exported
    assert body["shortname"] == "arena" and body["version"] == "v1"
    assert body["format"]["passed"] and body["sql_written"] is True
    kinds = [f["kind"] for f in body["files"]]
    assert kinds[0] == "eqg" and kinds[-1] == "bundle"
    assert {"eqmap", "sql", "sidecar", "install"} <= set(kinds)

    export_dir = vb.build_dir / EXPORT_DIR / "arena"
    for f in body["files"]:
        assert f["url"] == f"/api/zones/{ZONE}/v1/{EXPORT_DIR}/arena/{f['filename']}"
        r = client.get(f["url"])
        assert r.status_code == 200, f["url"]
        assert r.content == (export_dir / f["filename"]).read_bytes()
        assert client.head(f["url"]).status_code == 200

    sql = (export_dir / "arena.sql").read_text(encoding="utf-8")
    assert "short_name='arena'" in sql and "INSERT INTO doors" in sql
    assert "DELETE FROM spawn2" not in sql

    with zipfile.ZipFile(io.BytesIO(client.get(body["files"][-1]["url"]).content)) as z:
        names = z.namelist()
        assert names[0] == "arena.eqg" and names[-3:] == ["arena.sql", "arena.zone.json",
                                                          "INSTALL.txt"]
        assert any(n.startswith("maps/arena") for n in names)
        for n in names:
            assert z.read(n) == (export_dir / n).read_bytes(), n
        install = z.read("INSTALL.txt").decode("ascii")
    for f in MOVE_ASIDE:
        assert f.format(s="arena") in install
    assert "arena_chr.s3d" in install and "COPY" in install and "back up" in install.lower()

    # The build's own files never change.
    after = {k: v for k, v in _files(vb.build_dir).items() if not k.startswith(EXPORT_DIR)}
    assert after == before


def test_bundle_follows_a_repeat_export(exported):
    client, vb, _, _ = exported
    r = client.post("/api/export", json={"zone": ZONE, "version": "v1", "shortname": "Befallen",
                                         "clear_spawns": True})
    assert r.status_code == 200 and r.json()["shortname"] == "befallen"
    url = f"/api/zones/{ZONE}/v1/{EXPORT_DIR}/befallen/befallen.bundle.zip"
    with zipfile.ZipFile(io.BytesIO(client.get(url).content)) as z:
        assert "DELETE FROM spawn2" in z.read("befallen.sql").decode("utf-8")
    assert (vb.build_dir / EXPORT_DIR / "arena" / "arena.eqg").is_file()   # untouched


def test_unknown_name_and_build(server):
    client, _ = server
    r = client.post("/api/export", json={"zone": ZONE, "version": 1, "shortname": "arenna"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["close"] == closest("arenna") and "arena" in detail["close"]
    assert len(detail["close"]) <= 5
    assert client.post("/api/export", json={"zone": "nosuchzone", "version": 1}).status_code == 404
    assert client.post("/api/export", json={"zone": ZONE, "version": 9}).status_code == 404
    assert client.post("/api/export", json={"zone": "../x", "version": 1}).status_code == 400
    assert client.post("/api/export", json={"zone": ZONE, "version": "1x"}).status_code == 400


@pytest.mark.parametrize("path, status", [
    ("v1/export/arena/..%2Farena.eqg", 400),
    ("v1/export/arena/arena.eqg%0A", 400),
    ("v1/export/arena%0A/arena.eqg", 400),
    ("v1/export/a..b/a..b.eqg", 400),
    ("v1/export/arena/Arena.eqg", 400),
    ("v1/export/arena/stray.py", 400),
    ("v1/export/arena/befallen.eqg", 400),
    ("v1/export/arena/maps/arena.svg", 400),
    ("v1/export/arena/sub/arena.txt", 400),
    ("x1/export/arena/arena.eqg", 400),
    ("v1/export/arena/maps/arena_7.txt", 404),
    ("v1/export/qeynos/qeynos.eqg", 404),
    ("v2/export/arena/arena.bundle.zip", 404),
])
def test_file_route_refuses(exported, path, status):
    client = exported[0]
    r = client.get(f"/api/zones/{ZONE}/{path}")
    assert (r.status_code, r.content) == (status, b""), path


def test_cli_writes_the_same_export(exported, capsys):
    client, vb, _, _ = exported
    assert client.post("/api/export", json={"zone": ZONE, "version": 1}).status_code == 200
    assert client.get(f"/api/zones/{ZONE}/v1/{EXPORT_DIR}/arena/arena.bundle.zip").status_code == 200
    via_route = _files(vb.build_dir / EXPORT_DIR / "arena")
    cli.main(["export", str(vb.build_dir)])
    got = _files(vb.build_dir / EXPORT_DIR / "arena")
    assert "arena.bundle.zip" in got and sorted(got) == sorted(via_route)
    for name, data in got.items():
        assert _same(name, data) == _same(name, via_route[name]), name

    with pytest.raises(SystemExit) as info:
        cli.main(["export", str(vb.build_dir), "--shortname", "arenna"])
    assert info.value.code == 2
    assert "arena" in capsys.readouterr().err
