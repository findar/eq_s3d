"""The rooms seed on the CLI and the server (world-sockets task 8; Req 4.1, 4.4, 5.5).

``--rooms-seed`` and the server's ``rooms_seed`` (in the controls, or top-level as
"Reroll rooms" sends it) reach the sidecar's ``seeds`` block; a bad one is refused
before anything is written. A reroll re-derives the World from ``seed``.
"""

from __future__ import annotations

import json
import tempfile

import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod

SEED = 4
ROOMS = 9


@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


def _sidecar(build_dir, name):
    return json.loads((build_dir / f"{name}.zone.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------

def test_cli_rooms_seed_reaches_the_spec_and_the_sidecar(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    main.main(["generate", "r8", "--zone-type", "dungeon", "--seed", str(SEED), "--rooms", "3",
               "--decor", "none", "--rooms-seed", str(ROOMS), "--output", str(tmp_path)])
    (path,) = tmp_path.glob("r8_*/v1/r8.json")
    assert json.loads(path.read_text(encoding="utf-8"))["rooms_seed"] == ROOMS
    assert _sidecar(path.parent, "r8")["seeds"] == \
        {"seed": SEED, "rooms_seed": ROOMS, "decor_seed": SEED}


@pytest.mark.parametrize("value", ["-1", "2147483648", "1.5", "x"])
def test_cli_bad_rooms_seed_is_a_usage_error(value, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main.main(["generate", "r8", "--zone-type", "dungeon", "--rooms-seed", value,
                   "--output", str(tmp_path)])
    assert exc.value.code == 2
    assert "--rooms-seed" in capsys.readouterr().err
    assert not any(tmp_path.iterdir())


# ---------------------------------------------------------------------------
# The server
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"controls": {"zone_type": "dungeon", "rooms_seed": "x"}},
    {"controls": {"zone_type": "dungeon", "rooms_seed": -1}},
    {"controls": {"zone_type": "dungeon", "rooms_seed": True}},
    {"controls": {"zone_type": "dungeon"}, "rooms_seed": 2 ** 31},
    {"controls": {"zone_type": "dungeon"}, "rooms_seed": 1.5},
    {"controls": {"zone_type": "dungeon"}, "rooms_seed": "9"},
    {"mode": "prompt", "prompt": "a goblin warren", "rooms_seed": -1},
])
def test_a_bad_rooms_seed_is_a_400_naming_it_and_writes_nothing(client, body):
    r = client.post("/api/generate", json={"mode": "controls", **body})
    assert r.status_code == 400, r.text
    assert "rooms_seed" in r.json()["detail"], r.json()
    assert not any(app_mod.OUTPUT_DIR.iterdir())


@pytest.mark.parametrize("where", ["top", "controls"])
def test_the_server_builds_with_a_rooms_seed(client, where):
    """"Reroll rooms" sends the last request, ``seed`` pinned, a fresh top-level
    ``rooms_seed``; the controls may carry one too."""
    controls = {"zone_type": "dungeon", "room_count": 3, "decor": "none"}
    body = {"mode": "controls", "seed": SEED, "controls": controls}
    if where == "top":
        body["rooms_seed"] = ROOMS
    else:
        controls["rooms_seed"] = ROOMS
    r = client.post("/api/generate", json=body)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["seed"] == SEED and got["plan"]["rooms_seed"] == ROOMS
    side = _sidecar(app_mod.OUTPUT_DIR / got["id"] / "v1", got["id"])
    assert side["seeds"] == {"seed": SEED, "rooms_seed": ROOMS, "decor_seed": SEED}
