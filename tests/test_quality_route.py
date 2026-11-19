"""
tests/test_quality_route.py
---------------------------
The Quality_Block in the Server's responses and the CLI (zone-generator-quality Req 4, task 4;
umbrella 25.1-25.4, 25.9): generate, rebuild and edit responses carry ``quality`` equal to the
new version's sidecar entry, with the reason also in ``warnings`` when degraded and no quality
reason there otherwise; an edit that leaves the bands is accepted as ``edit_outside_bands``;
the versions listing carries ``quality: {degraded, reason}`` (null for a version without the
entry); the CLI prints a degraded build's reason, count and entries and exits 0, and nothing
for a passing one.

The bands are injected (``quality_bands`` through a wrapped ``generate_validated``): ``PASS``
bounds nothing, ``FAIL`` bounds ``cyclomatic`` out of reach, so a build's verdict is the
test's choice without hunting seeds. Seeds are pinned, so nothing is redrawn. Built ``.eqg``
files hold the client's art: they live in ``tmp_path`` only.
"""

from __future__ import annotations

import json
import tempfile

import pytest
from fastapi.testclient import TestClient

import generators.pipeline as pl
import main as main_mod
import server.app as app_mod
from ai.edits import RuleEditInterpreter
from generators.decor.stock import eq_path_from_env

pytestmark = pytest.mark.skipif(eq_path_from_env() is None,
                                reason="EQ_PATH is not set (no EQ install to read)")

CONTROLS = {"zone_type": "dungeon", "room_count": 5}
SEED = 4
PASS: dict = {}
FAIL = {"cyclomatic": (1000.0, None)}
REASONS = {pl.REASON_DEGRADED, pl.REASON_PINNED, pl.REASON_EDIT}


class Bands:
    """``generate_validated`` with the bands ``now`` holds (a caller's own bands win)."""

    def __init__(self):
        self.now = PASS

    def __call__(self, *a, **k):
        k.setdefault("quality_bands", self.now)
        return pl.generate_validated(*a, **k)


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("quality") / "web"
    root.mkdir()
    bands = Bands()
    mp.setattr(app_mod, "OUTPUT_DIR", root)
    mp.setattr(app_mod, "FAILURE_LOG", root.parent / "failures.jsonl")
    mp.setattr(app_mod, "get_edit_interpreter", RuleEditInterpreter)
    mp.setattr(app_mod, "generate_validated", bands)
    yield TestClient(app_mod.app), root, bands
    mp.undo()


def _sidecar(root, zone, n):
    return json.loads((root / zone / f"v{n}" / f"{zone}.zone.json").read_text(encoding="utf-8"))


def _check(build, root, *, degraded, reason=None):
    """``build`` (a generate/rebuild response) carries its sidecar's Quality_Block, its
    reason in ``warnings`` exactly when degraded (umbrella 25.2-25.4)."""
    q = build["quality"]
    assert q == _sidecar(root, build["id"], build["version"])["quality"]
    quality_warnings = [w for w in build["warnings"] if w in REASONS]
    if degraded:
        assert q["degraded"] is True and q["reason"] == reason
        assert q["out_of_band"] and q["out_of_band"][0]["metric"] == "cyclomatic"
        assert q["out_of_band"][0]["lo"] == 1000.0 and q["out_of_band"][0]["hi"] is None
        assert quality_warnings == [reason]
    else:
        assert q["degraded"] is False and q["reason"] is None
        assert q["out_of_band"] == [] and q["score"] == 0
        assert quality_warnings == []


def _generate(server, bands):
    client, root, holder = server
    holder.now = bands
    r = client.post("/api/generate", json={"controls": CONTROLS, "seed": SEED})
    assert r.status_code == 200, r.text
    return r.json()


def test_generate_carries_the_block(server):
    _, root, _ = server
    passed = _generate(server, PASS)
    _check(passed, root, degraded=False)
    failed = _generate(server, FAIL)
    _check(failed, root, degraded=True, reason=pl.REASON_PINNED)
    # The metrics are the meter's, whatever the bands.
    assert failed["quality"]["metrics"] == passed["quality"]["metrics"]


def test_rebuild_and_edits_carry_the_block(server):
    client, root, holder = server
    zone = _generate(server, PASS)["id"]

    # A decor rebuild of a passing parent that fails: measured, pinned reason (A4).
    holder.now = FAIL
    r = client.post("/api/rebuild", json={"zone": zone, "version": 1, "decor_seed": 77})
    assert r.status_code == 200, r.text
    rebuilt = r.json()
    assert rebuilt["version_info"]["how"] == "partial"
    _check(rebuilt, root, degraded=True, reason=pl.REASON_PINNED)

    # A partial edit leaving the bands: accepted as edit_outside_bands (umbrella 18.7).
    r = client.post("/api/edit", json={"zone": zone, "version": 1, "text": "much less decor"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True and body["how"] == "partial"
    _check(body["build"], root, degraded=True, reason=pl.REASON_EDIT)

    # A regenerate (planned again at a pinned seed) is measured as an edit too.
    r = client.post("/api/edit", json={"zone": zone, "version": 1,
                                       "ops": [{"op": "regenerate", "seed": SEED + 1}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True and body["how"] == "full"
    _check(body["build"], root, degraded=True, reason=pl.REASON_EDIT)

    # The listing: each version's {degraded, reason}; null without a sidecar entry (A3).
    path = root / zone / "v1" / f"{zone}.zone.json"
    side = json.loads(path.read_text(encoding="utf-8"))
    listing = {v["n"]: v["quality"]
               for v in client.get(f"/api/zones/{zone}/versions").json()["versions"]}
    assert listing[1] == {"degraded": False, "reason": None}
    assert listing[rebuilt["version"]] == {"degraded": True, "reason": pl.REASON_PINNED}
    assert listing[body["version"]] == {"degraded": True, "reason": pl.REASON_EDIT}
    try:
        path.write_text(json.dumps({k: v for k, v in side.items() if k != "quality"}),
                        encoding="utf-8")
        listing = {v["n"]: v["quality"]
                   for v in client.get(f"/api/zones/{zone}/versions").json()["versions"]}
        assert listing[1] is None
    finally:
        path.write_text(json.dumps(side, indent=2), encoding="utf-8")


def test_quality_warnings_keep_only_the_blocks_reason():
    passed = {"degraded": False, "reason": None}
    failed = {"degraded": True, "reason": pl.REASON_EDIT}
    assert app_mod._quality_warnings(["x", pl.REASON_PINNED], passed) == ["x"]
    assert app_mod._quality_warnings(["x", pl.REASON_EDIT], failed) == ["x", pl.REASON_EDIT]
    assert app_mod._quality_warnings(["x"], None) == ["x"]


# ---------------------------------------------------------------------------
# The CLI (umbrella 25.9)
# ---------------------------------------------------------------------------

def _cli(monkeypatch, tmp_path, capsys, bands):
    holder = Bands()
    holder.now = bands
    monkeypatch.setattr(main_mod, "generate_validated", holder)
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    main_mod.main(["generate", "q4", "--zone-type", "dungeon", "--seed", str(SEED),
                   "--rooms", "3", "--output", str(tmp_path)])      # no SystemExit: status 0
    return capsys.readouterr().out


def test_cli_prints_a_degraded_builds_entries(monkeypatch, tmp_path, capsys):
    out = _cli(monkeypatch, tmp_path, capsys, FAIL)
    (path,) = tmp_path.glob("q4_*/v1/q4.zone.json")
    q = json.loads(path.read_text(encoding="utf-8"))["quality"]
    (entry,) = q["out_of_band"]
    assert f"({pl.REASON_PINNED}), 1 metric(s) out of band" in out
    assert f"- cyclomatic = {entry['value']:.3f} (band 1000..-)" in out


def test_cli_prints_nothing_for_a_passing_build(monkeypatch, tmp_path, capsys):
    out = _cli(monkeypatch, tmp_path, capsys, PASS)
    assert "Quality" not in out and "out of band" not in out
