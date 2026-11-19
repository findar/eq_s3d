"""Districts through the CLI, the Server and the sidecar (districts spec task 5, Req 4.3,
4.4, A2): the sidecar's ``districts`` matches the spec, rooms carry their District and
Threshold corridors are flagged; a switch on another zone type builds with a
``districts_ignored`` note in ``warnings``; a rebuild or an edit of a districted version
keeps its Districts, and a saved spec's notes."""

from __future__ import annotations

import json
import tempfile

import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod
from generators.builder import with_district_notes
from generators.zone_spec import ZoneSpec

#: A districted dungeon that passes the gate on its pinned seed (two Districts).
CONTROLS = {"zone_type": "dungeon", "room_count": 10, "layout": "classic", "districts": True,
            "district_plan": ["temple"], "district_relationship": "factional"}
SEED = 2
CITY = {"zone_type": "city", "room_count": 6, "districts": True}


def _json(root, zone, n, kind):
    return json.loads((root / zone / f"v{n}" / f"{zone}.{kind}.json").read_text(encoding="utf-8"))


def _check_districts(side: dict, spec: dict) -> None:
    """The sidecar's District keys against the spec it built."""
    assert len(side["districts"]) >= 2
    assert side["districts"] == spec["districts"]
    owner = {rid: d["id"] for d in spec["districts"] for rid in d["room_ids"]}
    assert {r["id"]: r["district"] for r in side["rooms"]} == owner
    assert [c["id"] for c in side["corridors"]] == [c["id"] for c in spec["corridors"]]
    flagged = {c["id"] for c in side["corridors"] if c["threshold"]}
    assert flagged == {c["id"] for c in spec["corridors"] if c.get("threshold")}
    assert flagged == {d["threshold_corridor"] for d in spec["districts"] if d["id"]}


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """The Server in its own output folder, with a districted dungeon and a city with the
    switch on built as v1."""
    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("districts") / "web"
    root.mkdir()
    mp.setattr(app_mod, "OUTPUT_DIR", root)
    mp.setattr(app_mod, "FAILURE_LOG", root.parent / "failures.jsonl")
    client = TestClient(app_mod.app)
    d = client.post("/api/generate", json={"controls": CONTROLS, "seed": SEED})
    assert d.status_code == 200, d.text
    c = client.post("/api/generate", json={"controls": CITY, "seed": 3})
    assert c.status_code == 200, c.text
    yield client, root, d.json(), c.json()
    mp.undo()


def test_generate_writes_the_districts(server):
    _client, root, body, _city = server
    zone = body["id"]
    assert body["plan"]["districts"] is True
    assert body["plan"]["district_plan"] == [{"purpose": "temple"}]
    assert body["plan"]["district_relationship"] == "factional"
    side, spec = _json(root, zone, 1, "zone"), _json(root, zone, 1, "spec")
    _check_districts(side, spec)
    assert side["districts"][0]["purpose"] == "temple"
    assert side["warnings"] == body["warnings"]


def test_a_city_ignores_the_switch_with_a_note(server):
    _client, root, _body, city = server
    zone = city["id"]
    note = [w for w in city["warnings"] if w.startswith("districts_ignored:")]
    assert len(note) == 1
    side, spec = _json(root, zone, 1, "zone"), _json(root, zone, 1, "spec")
    assert note[0] in side["warnings"]
    assert spec["notes"] == note and "districts" not in spec
    assert "districts" not in side
    assert all("threshold" not in c for c in side.get("corridors") or ())


def test_a_bad_district_plan_is_a_400(server):
    client, *_ = server
    r = client.post("/api/generate", json={"controls": {**CONTROLS, "district_plan": "temple"},
                                           "seed": SEED})
    assert r.status_code == 400


@pytest.mark.parametrize("change", ["decor_seed", "rooms_seed"])
def test_a_rebuild_keeps_the_districts(server, change):
    client, root, body, _city = server
    zone = body["id"]
    r = client.post("/api/rebuild", json={"zone": zone, "version": 1, change: 77})
    assert r.status_code == 200, r.text
    n = r.json()["version"]
    side, spec = _json(root, zone, n, "zone"), _json(root, zone, n, "spec")
    _check_districts(side, spec)
    if change == "decor_seed":                  # partial: the parent's rooms, as they were
        assert side["districts"] == _json(root, zone, 1, "zone")["districts"]


def test_a_rebuild_keeps_the_notes(server):
    client, root, _body, city = server
    zone = city["id"]
    r = client.post("/api/rebuild", json={"zone": zone, "version": 1, "decor_seed": 77})
    assert r.status_code == 200, r.text
    n = r.json()["version"]
    assert r.json()["version_info"]["how"] == "partial"
    note = _json(root, zone, 1, "spec")["notes"]
    assert _json(root, zone, n, "spec")["notes"] == note
    assert [w for w in r.json()["warnings"] if w.startswith("district")] == note


@pytest.mark.parametrize("op", [{"op": "reroll_decor"}, {"op": "regenerate", "seed": SEED + 1}])
def test_an_edit_keeps_the_districts(server, op):
    client, root, body, _city = server
    zone = body["id"]
    r = client.post("/api/edit", json={"zone": zone, "version": "v1", "ops": [op], "seed": 5})
    assert r.status_code == 200, r.text
    out = r.json()
    if not out["applied"]:
        pytest.fail(f"edit not applied: {out}")
    n = out["version"]
    _check_districts(_json(root, zone, n, "zone"), _json(root, zone, n, "spec"))


def test_the_listing_names_the_districts(server):
    client, root, body, city = server
    v = client.get(f"/api/zones/{body['id']}/versions").json()["versions"][0]
    assert v["districts"] == [d["purpose"] for d in _json(root, body["id"], 1, "zone")["districts"]]
    v = client.get(f"/api/zones/{city['id']}/versions").json()["versions"][0]
    assert v["districts"] == []


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------

def _cli(tmp_path, *argv):
    main.main(["generate", "dz", *argv, "--seed", str(SEED), "--output", str(tmp_path)])
    (build,) = tmp_path.glob("dz_*/v1")
    return (json.loads((build / "dz.zone.json").read_text(encoding="utf-8")),
            json.loads((build / "dz.json").read_text(encoding="utf-8")))


def test_cli_districts(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    side, spec = _cli(tmp_path, "--rooms", "10", "--layout", "classic", "--districts",
                      "--district-purpose", "temple", "--district-relationship", "factional")
    _check_districts(side, spec)
    assert spec["districts"][0]["purpose"] == "temple"
    assert spec["districts"][0]["relationship"] == "factional"


def test_cli_city_notes_the_switch(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    side, spec = _cli(tmp_path, "--zone-type", "city", "--rooms", "6", "--districts")
    (note,) = spec["notes"]
    assert note.startswith("districts_ignored:") and note in side["warnings"]
    assert "districts" not in side and f"note: {note}" in capsys.readouterr().out


def test_cli_takes_at_most_three_purposes(tmp_path):
    with pytest.raises(SystemExit):
        main.main(["generate", "dz", "--districts", *["--district-purpose", "tomb"] * 4,
                   "--output", str(tmp_path)])


# ---------------------------------------------------------------------------
# The notes
# ---------------------------------------------------------------------------

def test_only_district_notes_ride_on_the_spec():
    spec = with_district_notes(ZoneSpec(name="z"), [
        "crosses_room: r1-r2", "districts_reduced: 3 requested, 2 fit the room graph",
        "district_purposes_relaxed: x", "stair_unplaced: r3-r4"])
    assert spec.notes == ["districts_reduced: 3 requested, 2 fit the room graph",
                          "district_purposes_relaxed: x"]
    assert ZoneSpec.from_dict(spec.to_dict()).notes == spec.notes
    assert "notes" not in ZoneSpec(name="z").to_dict()
