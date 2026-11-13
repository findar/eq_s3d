"""The stage commands (world-sockets task 10, Req 5.4): each runs from the previous one's
file, and the file it writes equals the full build's for the same seeds. One build each of a
root zone (dungeon) and an outdoor dungeon (hillside and ground Sockets), gate off."""

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

pytestmark = pytest.mark.slow

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
