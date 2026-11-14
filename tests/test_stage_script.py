"""The stage commands (world-sockets task 10, Req 5.4): each runs from the previous one's
file, and the file it writes equals the full build's for the same seeds. One build each of a
root zone (dungeon) and an outdoor dungeon (hillside and ground Sockets), gate off. On
version 2 (site-sockets task 10, Req 6.5): a wilderness's ``world`` and ``attach`` with a
rooms seed match its build, the World GLB marks each point Socket, and v1 files are refused."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.pipeline import generate_validated

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("stage", ROOT / "scripts" / "stage.py")
stage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stage)

SEED = 3
ZONE_TYPES = ("dungeon", "outdoor_dungeon")


@pytest.fixture(scope="module", params=ZONE_TYPES)
def build(request, tmp_path_factory):
    zt = request.param
    out = tmp_path_factory.mktemp(f"stage_{zt}")
    plan = lambda s: plan_to_spec(ZonePlan(name=f"st_{zt}", zone_type=zt), seed=s)  # noqa: E731
    vb = generate_validated(plan, zone_type=zt, zone_id=f"z_{zt}", seed=SEED, output_dir=out / "build",
                            write_glb=False, validate_enabled=False, failure_log=None)
    return zt, vb.build_dir, out / "stage"


def _text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.mark.slow
def test_each_stage_reruns_from_the_last_and_matches_the_build(build):
    zt, built, out = build
    name = f"st_{zt}"
    assert stage.main(["world", name, "--zone-type", zt, "--seed", str(SEED), "--out", str(out)]) == 0
    assert _text(out / f"{name}.world.json") == _text(built / f"{name}.world.json")

    assert stage.main(["attach", str(out / f"{name}.world.json"), "--out", str(out)]) == 0
    assert _text(out / f"{name}.attach.json") == _text(built / f"{name}.attach.json")

    assert stage.main(["rooms", str(out / f"{name}.attach.json"), "--out", str(out)]) == 0
    assert _text(out / f"{name}.rooms.json") == _text(built / f"{name}.rooms.json")
    assert (out / f"ter_{name}.ter").stat().st_size > 0

    assert stage.main(["decor", str(out / f"{name}.rooms.json"), "--out", str(out)]) == 0
    rooms = json.loads(_text(out / f"{name}.rooms.json"))["rooms"]
    decor = json.loads(_text(out / f"{name}.decor.json"))
    assert [r["id"] for r in decor["rooms"]] == [r["id"] for r in rooms]
    for kind in ("world", "attach", "rooms", "decor"):
        assert (out / f"{name}.{kind}.glb").read_bytes()[:4] == b"glTF"


WILD_SEED, ROOMS_SEED = 1000, 9


@pytest.mark.slow
def test_wilderness_world_and_attach_match_the_build_on_a_rooms_seed(tmp_path):
    name = "st_wild"

    def factory(s):
        spec = plan_to_spec(ZonePlan(name=name, zone_type="wilderness"), seed=s)
        spec.rooms_seed = ROOMS_SEED
        return spec

    vb = generate_validated(factory, zone_type="wilderness", zone_id="z_wild", seed=WILD_SEED,
                            output_dir=tmp_path / "build", write_glb=False, validate_enabled=False,
                            failure_log=None)
    built, out = vb.build_dir, tmp_path / "stage"
    assert stage.main(["world", name, "--zone-type", "wilderness", "--seed", str(WILD_SEED),
                       "--out", str(out)]) == 0
    assert _text(out / f"{name}.world.json") == _text(built / f"{name}.world.json")
    assert stage.main(["attach", str(out / f"{name}.world.json"), "--rooms-seed", str(ROOMS_SEED),
                       "--out", str(out)]) == 0
    attach = _text(out / f"{name}.attach.json")
    assert attach == _text(built / f"{name}.attach.json")
    sites = [s for a in json.loads(attach)["attachments"] if a["kind"] == "ground"
             for s in a["sites"]["sites"]]
    assert sites and all(s["socket"].startswith("site") for s in sites)


def test_world_glb_marks_each_point_with_a_post():
    from generators.world import world_for
    world = world_for("wilderness", WILD_SEED)
    points = [s for s in world.sockets if s.kind == "site"]
    assert points
    v, f, _c = stage.points_part(world)
    assert len(v) == 8 * len(points) and len(f) == 12 * len(points)
    for k, s in enumerate(points):
        box = v[8 * k:8 * k + 8]
        assert abs(box[:, 0].mean() - s.x) < 1e-6 and abs(box[:, 1].mean() - s.y) < 1e-6
        assert box[:, 2].min() == pytest.approx(s.z)
        assert box[:, 2].max() - s.z == pytest.approx(stage.POST_HEIGHT)
    # the column marks are for the other Sockets only
    others = [s for s in world.sockets if s.kind != "site"]
    assert len(stage.sockets_part(world)[0]) == 8 * len(others)


@pytest.mark.parametrize("which", ["world", "attach"])
def test_version_1_files_are_refused_with_the_readers_message(tmp_path, which):
    from generators.world import world_for
    from generators import stages
    world = world_for("wilderness", WILD_SEED)
    wpath = tmp_path / "w.world.json"
    if which == "world":
        d = json.loads(world.to_json())
        d["version"] = 1
        wpath.write_text(json.dumps(d), encoding="utf-8")
        argv = ["attach", str(wpath), "--out", str(tmp_path)]
    else:
        wpath.write_text(world.to_json(), encoding="utf-8")
        apath = tmp_path / "w.attach.json"
        apath.write_text(json.dumps({"version": 1, "attachments": []}), encoding="utf-8")
        argv = ["rooms", str(apath), "--out", str(tmp_path)]
        assert stages.ATTACH_VERSION == 2
    with pytest.raises(SystemExit) as e:
        stage.main(argv)
    msg = str(e.value.code)
    assert "version 1" in msg and "version 2" in msg
    assert str(wpath if which == "world" else tmp_path / "w.attach.json") in msg
