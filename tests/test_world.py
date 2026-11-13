"""The World and Socket types (world-sockets Req 1.1, 1.4, 1.5, 5.3; design P1)."""

from __future__ import annotations

import dataclasses
import inspect
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


# -- the World stage (task 3; design P2, P3) ---------------------------------

LANDSCAPE_SEEDS = [(7, None), (3, {"E": "river"}), (6, {"N": "zoneline"})]
SOCKETS = {"dungeon": [("root", "root")], "city": [("root", "root")],
           "wilderness": [("ground", "ground")],
           "outdoor_dungeon": [("hill0", "hillside"), ("ground", "ground")]}


def _grid_zs(ter, shape) -> np.ndarray:
    n = shape[0] * shape[1]
    return np.array([v.z for v in ter.vertices[:n]], dtype=np.float64).reshape(shape)


def test_world_stage_reads_only_world_inputs():
    params = list(inspect.signature(W.world_for).parameters)
    assert params == ["zone_type", "seed", "biome", "edges", "zone_size", "landform"]


@pytest.mark.parametrize("zone_type", sorted(SOCKETS))
def test_each_zone_type_offers_its_sockets_and_the_same_text(zone_type):
    w = W.world_for(zone_type, 11, edges={"E": "river"})
    text = w.to_json()
    assert W.world_for(zone_type, 11, edges={"E": "river"}).to_json() == text
    assert World.from_json(text) == w
    assert [(s.id, s.kind) for s in w.sockets] == SOCKETS[zone_type]
    assert (w.terrain is None) == (zone_type in ("dungeon", "city"))


@pytest.mark.parametrize("seed,edges", LANDSCAPE_SEEDS)
def test_wilderness_heights_exact(seed, edges):
    from generators.wilderness.build import build_wilderness_ter, landscape_for, wilderness_spec

    spec = wilderness_spec("w", seed, edges)
    w = World.from_json(W.world_of(spec).to_json())
    assert w.to_json() == W.world_for("wilderness", seed, edges=edges).to_json()
    t = w.terrain
    assert W._same_floats(t.heights, _grid_zs(build_wilderness_ter(spec, "t", 1), t.heights.shape))
    assert W._same_floats(t.undrowned, np.asarray(landscape_for(spec).bowl.heights, np.float64))
    assert w.spawn == tuple(spec.safe_point) == (w.socket("ground").x, w.socket("ground").y,
                                                w.socket("ground").z)
    assert w.regions == [dataclasses.asdict(r) for r in spec.regions]


@pytest.mark.parametrize("seed,edges", LANDSCAPE_SEEDS)
def test_outdoor_dungeon_host_and_entry_exact(seed, edges):
    from generators.outdoor_dungeon import _UNDIGGABLE, host_envelope, outdoor_dungeon_spec
    from generators.wilderness.build import build_wilderness_ter

    spec = outdoor_dungeon_spec("od", seed, edges)
    w = World.from_json(W.world_of(spec).to_json())
    assert w.to_json() == W.world_for("outdoor_dungeon", seed, edges=edges).to_json()
    host = build_wilderness_ter(spec, "t", 1)            # the host TER, before the Apron
    t = w.terrain
    assert W._same_floats(t.heights, _grid_zs(host, t.heights.shape))
    env = host_envelope(spec, host)
    hill = w.socket("hill0")
    assert (hill.x, hill.y) == env.entry and hill.side == spec.wilderness["landform"]["approach"]
    assert hill.z == float(env.surface(*env.entry))
    assert [tuple(p) for p in hill.ground["footprint"]] == list(env.footprint)
    assert hill.ground["rock_cover"] == env.rock_cover
    assert hill.ground["landform"] == spec.wilderness["landform"]
    near = np.pad(np.isin(t.node_type, _UNDIGGABLE), 1)
    keep = {(i, j) for i in range(t.heights.shape[0]) for j in range(t.heights.shape[1])
            if near[i:i + 3, j:j + 3].any()}
    assert {tuple(p) for p in hill.ground["undiggable"]} == keep
    # The Spawn before the Apron: the Apron only ever lowers the spec's.
    assert w.spawn[:2] == tuple(spec.safe_point[:2]) and spec.safe_point[2] <= w.spawn[2]
    # One landscape (task 20): the spec's regions and water are the World's.
    assert w.regions == [dataclasses.asdict(r) for r in spec.regions]
    assert spec.water_level == t.water_level


def test_apron_spawn_is_never_under_the_shipped_floor(monkeypatch):
    """Task 20: a Spawn the Apron lowers is stored as the 32-bit float at or above the dug
    ground, so the TER's (32-bit) floor is never above it (fortress troll seed 3 failed the
    format check's ``safe_point`` by 4.8e-7 u). A fake Apron digs 31.103 u everywhere."""
    from types import SimpleNamespace

    from generators import outdoor_dungeon as od
    from generators import stages

    z = np.full((4, 4), -5.009791374206543)              # float32-exact, as the bowl's are
    grid = SimpleNamespace(z=z, origin=(-60.0, -60.0), res=40.0)
    monkeypatch.setattr(od, "_apron", lambda g, e: (g.z - 31.103078365325928, False))
    world = SimpleNamespace(spawn=(-20.0, -20.0, float(z[1, 1])))
    edit = stages.apron_edit(world, SimpleNamespace(id="hill0"), grid, None)
    sz = edit.spawn[2]
    assert float(np.float32(sz)) == sz                   # what the TER can store
    assert sz >= -5.009791374206543 - 31.103078365325928
    assert float(np.float32(z[1, 1] - 31.103078365325928)) <= sz   # the TER's floor there


def _spawn_vertex(w: World):
    t = w.terrain
    i, j = (round((v - o) / t.res - 0.5) for v, o in zip(w.spawn[:2], t.origin))
    return i, j


def test_outdoor_dungeon_reads_one_landscape_seeds_0_39():
    """Task 20: for seeds 0-39 an outdoor dungeon's World (``world_for`` alone, no TER and no
    planning) takes its Spawn, regions and water from the placed Landform's landscape, the one
    its terrain is, and the Spawn stands on that terrain's ground."""
    from generators.wilderness.bowl import _spawn_world_point
    from generators.wilderness.build import landscape_for, wilderness_spec
    from generators.wilderness.matrix import DEFAULT_HOST_HILL, Landform
    from generators.wilderness.matrix import OUTDOOR_DUNGEON_ZONE_SIZE as SIZE

    for seed in range(40):
        w = W.world_for("outdoor_dungeon", seed)
        placed = Landform.from_dict(w.recipe["landform"])
        assert w.socket("hill0").ground["landform"] == w.recipe["landform"], seed
        # Asked for with the request or with what it places, the World is the same.
        assert W.world_for("outdoor_dungeon", seed, landform=placed).to_json() == w.to_json()
        land = landscape_for(wilderness_spec("p", seed, landform=placed, zone_size=SIZE))
        assert land.matrix.landform == placed, seed
        assert w.spawn == _spawn_world_point(land.synth, land.matrix, land.bowl.heights), seed
        assert w.terrain.water_level == float(land.matrix.water_level), seed
        assert w.regions[:len(land.bowl.regions)] == [dataclasses.asdict(r)
                                                       for r in land.bowl.regions], seed
        i, j = _spawn_vertex(w)
        assert w.spawn[2] == w.terrain.heights[i, j], seed
        assert DEFAULT_HOST_HILL.approach is None   # the request is the unplaced hill
