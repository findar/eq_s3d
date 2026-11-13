"""The World and Socket types (world-sockets Req 1.1, 1.4, 1.5, 5.3; design P1)."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from generators import world as W
from generators.world import Socket, Terrain, World

ODD = 0.1 + 0.2          # 0.30000000000000004: survives only if nothing rounds


def _terrain() -> Terrain:
    rng = np.random.default_rng(5)
    h = rng.normal(0.0, 37.0, (5, 4))
    h[0, 0], h[0, 1], h[1, 1], h[4, 3] = ODD, -0.0, np.nan, 1e-300
    types = np.array([["mountain_rim"] * 3, ["plains", "water", "river"],
                      ["cliff", "lava", "zoneline_gap"], ["plains"] * 3], dtype=object)
    rim = types == "mountain_rim"
    return Terrain(origin=(-ODD, -600.0), res=40.0, heights=h, node_type=types,
                   rim_seal=rim, playable_interior=~rim & (types == "plains"), water_level=-12.5)


def _hillside() -> Socket:
    return Socket("hill0", "hillside", x=ODD, y=-0.0, z=17.123456789012345, yaw=-math.pi / 2,
                  side="S", width=40.0, height=36.0, accepts=("dungeon",),
                  ground={"footprint": [(0.1, 0.2), (ODD, -0.0), (1e17, 3.0)], "rock_cover": 24.0,
                          "origin": (-600.0, -600.0), "res": 40.0, "undiggable": [[0, 1], [3, 2]]})


def _ground() -> Socket:
    return Socket("ground", "ground", x=12.0, y=ODD, z=-0.0, accepts=("site",),
                  ground={"keep_clear": [(1.0, 2.0, 3.0, 4.0, ODD)], "spawn": (12.0, ODD, -0.0)})


WORLDS = {
    "root": lambda: World(recipe={"zone_type": "dungeon", "seed": 7},
                          sockets=[Socket("root", "root", accepts=("dungeon", "city"))]),
    "hillside+ground": lambda: World(
        recipe={"zone_type": "outdoor_dungeon", "seed": 3, "biome": "forest", "zone_size": 1200,
                "edges": {"N": "mountain"}, "landform": {"radius": 250.0, "relief": ODD}},
        terrain=_terrain(), regions=[{"kind": "water", "min": [0.0, -0.0, ODD]}],
        spawn=(ODD, -0.0, 4.5), sockets=[_hillside(), _ground()]),
    "ground": lambda: World(recipe={"zone_type": "wilderness", "seed": 1}, terrain=_terrain(),
                            spawn=(0.0, 0.0, 1.0), sockets=[_ground()]),
    "door": lambda: World(sockets=[Socket("door0", "door", x=ODD, width=8.0, height=12.0,
                                          accepts=("room",))]),
}


@pytest.mark.parametrize("name", sorted(WORLDS))
def test_round_trips_exactly(name, tmp_path):
    w = WORLDS[name]()
    text = w.to_json()
    path = tmp_path / f"{name}.world.json"
    W.save(path, w)
    back = W.load(path)
    assert back == w
    assert back.to_json() == text == path.read_text(encoding="utf-8")
    assert json.loads(text)["version"] == W.VERSION


def test_floats_are_not_rounded():
    back = World.from_json(WORLDS["hillside+ground"]().to_json())
    hill, ground = back.socket("hill0"), back.socket("ground")
    assert hill.x == ODD and math.copysign(1.0, hill.y) == -1.0
    assert hill.ground["footprint"][1][0] == ODD
    assert math.copysign(1.0, hill.ground["footprint"][1][1]) == -1.0
    assert ground.ground["keep_clear"][0][4] == ODD
    assert back.spawn[0] == ODD and math.copysign(1.0, back.spawn[1]) == -1.0
    t = back.terrain
    assert t.heights[0, 0] == ODD and math.copysign(1.0, t.heights[0, 1]) == -1.0
    assert t.heights[4, 3] == 1e-300 and np.isnan(t.heights[1, 1])
    assert t.origin[0] == -ODD and t.heights.dtype == np.float64
    assert t.node_type[2, 1] == "lava" and t.rim_seal[0].all() and not t.rim_seal[1:].any()


def test_text_is_stable_and_one_row_per_line():
    text = WORLDS["ground"]().to_json()
    assert '"heights": [\n' in text and '"rim_seal": [\n   "###",\n' in text
    assert "null" in text and "NaN" not in text
    keys = list(json.loads(text))
    assert keys == sorted(keys)


def test_another_version_is_refused_by_name(tmp_path):
    path = tmp_path / "old.world.json"
    W.save(path, World(version=W.VERSION + 1, sockets=[Socket("root", "root")]))
    with pytest.raises(ValueError, match=rf"old\.world\.json.*World version {W.VERSION + 1}.*version {W.VERSION}"):
        W.load(path)
    d = WORLDS["root"]().to_dict()
    d["sockets"][0]["version"] = 0
    path.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError, match=rf"old\.world\.json.*Socket version 0.*version {W.VERSION}"):
        W.load(path)


def test_unknown_kind_and_non_finite_numbers_are_refused():
    with pytest.raises(ValueError, match="kind"):
        Socket("x", "tower")
    with pytest.raises(ValueError):
        Socket("x", "root", ground={"r": float("inf")})
    t = _terrain()
    t.heights[2, 2] = np.inf
    with pytest.raises(ValueError):
        World(terrain=t).to_json()


def test_loads_without_the_wilderness_or_outdoor_dungeon():
    code = ("import sys, generators.world; "
            "print([m for m in sys.modules if m.startswith(('generators.wilderness', 'generators.outdoor_dungeon'))])")
    root = Path(__file__).resolve().parents[1]
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=root)
    assert out.stdout.strip() == "[]"
